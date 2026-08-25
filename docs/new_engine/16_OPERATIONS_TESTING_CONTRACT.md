# 16 运维、测试与发布门禁

> V6 边界：本文的 M1 必测项支持内部 / 封闭交付；完整浏览器、capacity / soak、五范围恢复与公开运营资料必须在独立 `PublicV1Gate`（`RELEASE-001`）中重新执行。M1-B 通过不等于 Public V1 可发布。

> 状态：首发实施契约。本文把稳定性、可维护性、安全性和可复现验收落实为工程门禁。任何首发候选版本都必须满足本文，而不是只通过功能演示。

## 1. 环境一致性

- 开发、测试、CI 和生产主线统一使用 PostgreSQL 18；M0 基线固定为 18.4，升级小版本时必须在同一变更中同步本合同、Compose 与 CI。
- Python 版本与项目锁文件一致，最低为 3.14；M0 基线固定为 3.14.2。
- Redis 与 Celery 不是首发必需项。
- 未使用 Redis channel layer 时，只运行一个 Daphne / ASGI 游戏进程。
- 配置通过环境变量或密钥管理注入，不提交真实凭据。

## 2. CI 门禁

每次合并必须执行：

- 后端格式与静态检查
- 后端类型检查
- PostgreSQL 单元与集成测试
- 数据库迁移检查
- 协议、Registry、Blueprint 与状态机契约测试
- 前端格式、类型、单元和构建检查
- 首发纵切端到端测试
- XKX100 黄金行为与转换 fixture 回归测试
- 依赖与密钥泄漏扫描

SQLite 结果不能替代 PostgreSQL 主线测试。

### 2.1 会话与认证强制矩阵

PostgreSQL 契约测试和端到端测试必须覆盖：

- `POST /api/v1/auth/register` 精确方法/路径、账号名规范化、密码校验、原子 User/GameAccount 创建，以及注册后零 AuthSession/token/Cookie。
- request id 与 Refresh `Idempotency-Key` 的安全格式正反例，以及非 active Presence 调用 `state.sync` 被拒绝。
- `POST /api/v1/auth/login|refresh|logout` 精确方法/路径、全部开户/认证响应 `Cache-Control: no-store`、H5 refresh Cookie 属性和 token 不进入日志。
- register/login/refresh/logout 四个端点都拒绝未允许 Origin；跨源 register/login 必须覆盖 CSRF/session swapping 反例。
- 登录生成随机 opaque `device_id`，测试确认它不等于也不派生自 IP、User-Agent 或浏览器指纹；认证失败只暴露稳定 code。
- `session.authenticate` 同 ConnectionSession 幂等补绑、payload 冲突，以及跨 ConnectionSession 重新验证和绑定。
- enter/resume/recover/takeover 在 pending 准备、提交、激活和 finalization 各边界的故障注入；不得出现可收命令的 pending Presence 或可重放的虚假成功。
- 页面重载丢失内存 ticket 后，`presence.recover` 只允许同一 AuthSession 恢复自己的 active/grace 租约，递增 generation、撤销旧 ticket、签发新 ticket并返回完整 snapshot；无自有租约与跨 AuthSession 请求统一失败，不得泄露占用详情、退化为 enter 或自动 takeover。
- 在提交后激活前及激活后 finalization 前杀死 owner；启动扫描/超时 sweeper 必须关闭新 snapshot、撤销新 ticket、稳定失败终结、取消成功 outbox 并释放唯一占用。
- outbox worker 在 `activation_pending / active / compensated` 三态竞跑；成功类只在 active 投递一次，补偿时取消，takeover 的 committed revocation 可提交后投递且不声称新端成功。
- takeover 回滚保持旧端可用；提交后 outbox 投递失败不回滚，旧端通过下一请求校验或重连收敛。
- 绑定型成功跨 ConnectionSession 重放只返回 `resume_required`，旧 snapshot 不得应用，新 request id 的 resume 成功后才激活。
- action/ui/sync 等 Presence-required 终结在 generation 改变时返回 `REQUEST_CONTEXT_CHANGED`；`state.sync` 跨连接或 barrier seq 推进后省略旧 snapshot 并要求新 request id。
- refresh 同 key 同请求安全重放、同 key 请求冲突、successor superseded，以及不同 key 重用 used token 的 replay 撤销。
- `RequestTerminalRecord` 与 refresh terminal 在重试窗口、active secret reference、family 绝对到期和清理缓冲各边界的保留/清理测试；pending 不得被普通清理器删除。
- refresh 提交后丢响应并重载时复用持久 key，多标签页保持 single-flight；不确定 cookie 遇 conflict/superseded 时安全 logout，不用新 key 触发误 replay。
- M1 后台 RecoveryCode 流程覆盖角色权限、重新认证、reason/support case 和审计：冻结 / 撤销可用，最小修复只在同一权威服务验证玩家仍持有效 code 后成功。无 code、越权、并发消费、密码与 code 均丢失或事务故障时，不得改密、签发凭据、复活会话或把账号重分配给其他 User。

## 3. 可观测性

至少采集：

- HTTP 与 WebSocket 请求量、延迟和错误率
- 在线连接、AuthSession 与 Presence 数量
- 房间广播和聊天投递失败
- 战斗结算耗时与错误码
- 调度积压、重试和失败
- 数据库连接池、慢查询和锁等待
- 内容发布、回滚和 apply job 结果

日志使用结构化格式和关联 id。指标、日志与审计记录必须区分用途和保留策略。

## 4. 脱敏与审计

禁止在普通日志、审计 payload 或异常上报中记录：

- access / refresh token
- resume ticket
- 密码和验证码
- Cookie、Authorization header
- 手机号明文
- 私聊正文的无授权副本

审计 payload 采用字段白名单。后台改数、封禁、经济修正、高价值物品发放和内容发布必须记录操作者、原因、前后差异与关联请求。

## 5. 优雅停机与恢复

停机顺序：

1. 停止接受新连接与后台写操作。
2. 向在线连接发送维护事件。
3. 等待有界时间完成正在提交的事务。
4. 停止领取新的持久任务。
5. 提交可提交结果并关闭数据库连接。
6. 结束进程。

重启后先补偿死亡 runtime 遗留的 `activation_pending`，再清理过期 snapshot、恢复持久任务并执行健康检查；完成前不接受新的 Presence 建立请求。活跃战斗按安全策略结束，不恢复半完成攻击。

## 6. 备份与恢复

- PostgreSQL 执行定时全量备份与可验证的增量/WAL 策略。
- 发布前后保留内容批次和关键数据快照。
- 备份必须加密、限制访问并设置保留周期。
- 每个部署环境必须在发布审批前由负责人批准明确的 RPO 与 RTO 目标。
- 每个发布周期至少在隔离环境完成一次恢复演练。
- 恢复验收包括账号、角色、世界拓扑、内容批次和审计链完整性。

只有生成备份文件不算通过。演练必须记录实测恢复点与恢复时长，并证明两者均满足已批准目标；目标未批准或演练超标都阻断发布。

M0 可以先用 `m0_infrastructure` 级隔离演练验证 PostgreSQL 客户端版本、快照 dump、临时库 restore、schema、迁移历史、逐表行数和清理流程，并由恢复预算绑定报告路径与 SHA-256。只要账号、角色、世界拓扑、内容批次或审计链任一范围尚未实现、没有非空样本或未通过校验，该报告必须保持 `release_gate_eligible=false`，不得计作本节发布恢复验收。后续发布候选必须重新执行覆盖全部五个范围的演练。

除非已批准 profile 采用更严格目标，首发生产环境固定 RPO 不超过 15 分钟、RTO 不超过 60 分钟，并至少保留 7 份每日备份和 4 份每周备份。

降低这些目标必须修改 `requirements_v6.md`；部署配置和审批记录只能提高目标。

## 7. 性能与容量

M0 必须版本控制 Public V1 使用的 `capacity_profile`，记录环境、数据集、负载模型、采样窗口和阈值。M1-B 可做内部抽样，但完整 profile 证据只在 `PublicV1Gate` 重新执行。默认 profile 为：

- 应用 4 vCPU / 8 GiB，PostgreSQL 4 vCPU / 8 GiB，同区域网络，生产构建，不启用 Redis。
- 10000 个账号与角色、10000 个 Blueprint revision、100000 个 Item Entity。
- 200 条 WebSocket、100 个 active Presence、25 场并行战斗。
- 每秒 5 次注册/登录与 20 条公共聊天消息的 5 分钟突发。
- 基线负载持续 2 小时。

首发压测至少覆盖：

- 并发登录与重连
- 房间广播
- 公共频道突发消息
- 多场并行战斗
- 背包与装备并发写
- 调度任务到期尖峰
- Blueprint 发布和样板区域加载

容量报告必须记录硬件、数据库版本、数据规模、并发模型、P50/P95/P99、错误率和瓶颈。未定义环境的“性能良好”不算验收。

默认通过阈值：

- 注册、登录和 refresh 的服务端 P95 不超过 750 ms，错误率低于 1%。
- 非调度型 Action 终结 P95 不超过 300 ms。
- 公共聊天从服务端接收到可交付事件的 P95 不超过 500 ms。
- 新连接建立后的完整状态重建 P95 不超过 2 秒。
- 两小时基线中不得出现数据不一致、重复结算、未处理异常或非计划断线。

延迟不含客户端公网传输和显式 Scheduler 等待。采用更严格目标不需要修改需求；放宽任一最低目标必须先修改 `requirements_v6.md`。

## 8. XKX100 参考基线

项目必须维护可由 CI 读取、版本化且不可原地覆盖的 `source_snapshot.json`。它至少记录：

- 不可变 `source_snapshot_id`；运行配置中的 `reference_snapshot_id` 必须解析到该 id。
- 哈希算法、按相对路径排序的完整逐文件清单、每个文件原始字节 SHA-256 与文件树聚合 SHA-256。
- 纳入/排除规则、编码探测、扫描规则、生成工具版本、来源说明与获取权限。

所有清单 path 先规范为 Unicode NFC、`/` 分隔的相对路径；拒绝绝对路径、空段、`.`、`..` 与控制字符。数组内 path 唯一，并按规范 path 的 UTF-8 字节升序排序。

`tree_sha256` 的输入对象固定为 `{"files":[{"path":...,"sha256":...}]}`；每项 hash 对原始字节计算。对象经 RFC 8785/JCS 编码为无 BOM UTF-8，再计算小写十六进制 SHA-256。

世界 fixture manifest 固定为 `xkx100-village-alley-v1`。它的 `root_files` 必须恰好是以下相对路径的排序集合，不能只校验“数量为五”：

- `d/village/alley1.c`
- `d/village/alley2.c`
- `d/village/npc/dipi.c`
- `d/village/npc/obj/cloth.c`
- `d/village/npc/punk.c`

manifest 还必须保存独立 `dependency_files`，覆盖五个 roots 的完整 transitive include、inherit 与静态 runtime helper 闭包。依赖不扩写 root whitelist，也不参与 fixture 定义计数。

root/dependency 每项都保存规范 path 与原始字节 SHA-256；两个数组各自 path 唯一且互斥。`root_files` 与 `dependency_files` 必须分别按规范 path 的 UTF-8 字节升序排序，不能合并排序或依赖输入遍历顺序。

`aggregate_sha256` 的输入固定为 `{"root_files":[{"path":...,"sha256":...}],"dependency_files":[...]}`，使用同一 RFC 8785/JCS + UTF-8 + 小写 SHA-256 算法。

manifest 还必须记录 `alley1.east -> sroad3` external boundary、定义计数与初始运行时计数。

定义计数固定为 2 个 `kind=room`、2 个独立 `kind=exit`、1 条 Room external boundary、2 NPC、1 Item；运行时固定为 2 Room、2 个可通行 Exit Entity、2 NPC、2 个源自同一 `cloth.c` 定义且初始由 NPC 穿戴的 Item。

两个 Room 的 compiled `spawn_entries` 必须以 exact NPC refs 产生上述两个 NPC；两个 NPC 的 compiled `item_loadout` 必须以 exact Item ref 产生上述两个 Item 与 EquipmentBinding。空 skill/item loadout 必须显式为 `[]`。

同一 `source_snapshot_id` 下必须独立冻结 `xkx100-skill-combat-v1` manifest。它把受审 skill/command/feature 入口列为 roots，把完整 transitive include/inherit/helper 闭包列为 dependency_files，并使用同一聚合算法。

两个 manifest 可共享 dependency path，但同一路径 hash 必须一致。skill/command 不得成为 world root；world root 的支持文件只进入 dependency_files，不生成额外 fixture 定义。

复合验收 bundle 只引用两个 manifest 的名称、版本、`source_snapshot_id` 与聚合哈希，不复制或合并文件清单。任一 dependency 未闭合，或 id、分类、逐文件哈希、聚合哈希、边界、计数不一致时，转换和黄金验收必须在产生发布制品前失败。

完整战斗初始态不写入 world manifest。它必须属于复合验收 bundle 内的 golden case，或由该 case 以不可变 id + SHA-256 引用；world manifest 只承载五个 roots、其 dependency closure、边界、计数和哈希，不承载 skill roots 或武学规则。

黄金差分必须固定 RNG 种子、冻结时钟、时区和完整初始状态。golden case 的 `initial_state` 至少必须显式枚举以下字段；空集合或无战斗状态也要写成 `[] / {} / null`，不能靠默认值或 fixture 代码隐式补齐：

- `instance_id`，标识本用例唯一的游戏实例。下列全部 Entity、binding 与 materialization 都必须属于该实例。
- `character.id / instance_id / location_entity_id / lifecycle_state / character_version / inventory_version / stats`，其中 `stats` 是用例读取的全部角色数值键和值。
- `static_entity_bindings[].instance_id / blueprint_head_id / blueprint_revision_id / entity_id / state_version`，覆盖两个 Room 与两个 Exit。
- `rooms[].id / instance_id / blueprint_revision_id / location_entity_id / lifecycle_state / external_exit_boundaries`；Room 的 `location_entity_id` 必须为 null，外部 `east -> sroad3` 不得出现在 Exit Entity 集合。
- `exits[].id / instance_id / blueprint_revision_id / location_entity_id / lifecycle_state / target_room_id / direction / aliases`。`location_entity_id` 是 source Room，source/target 必须匹配 Exit revision 的 exact dependencies。
- `spawn_materializations[].instance_id / room_entity_id / room_blueprint_revision_id / spawn_entry_id / ordinal / target_blueprint_revision_id / spawned_entity_id / state_version`。
- `npcs[].id / instance_id / blueprint_revision_id / location_entity_id / lifecycle_state / stats / skills / jifa_bindings / prepare_bindings`。
- `npcs[].skills[]` 与 `character.skills[]`：`id / actor_entity_id / skill_head_id / skill_blueprint_revision_id / level / state_version`。
- `npcs[].jifa_bindings[]` 与 `character.jifa_bindings[]`：`actor_entity_id / enable_slot / actor_skill_id / state_version`。
- `npcs[].prepare_bindings[]` 与 `character.prepare_bindings[]`：`actor_entity_id / enable_slot / combine_order / actor_skill_id / state_version`。
- `items[].id / instance_id / blueprint_revision_id / location_entity_id / lifecycle_state / quantity / state_version`。
- `equipment_bindings[].wearer_entity_id / equip_slot / item_instance_id / state_version`。
- `conditions[].target_ref / condition_definition_revision_id / effect_type_key / effect_type_version / payload / stack_count / timing`。
- `scheduler.pending_jobs / combat.instance / combat.participants / combat.targets / combat.busy`，首场战斗前必须明确为空或给出完整值。
- `environment.locale / environment.source_encoding / environment.normalization / environment.timezone / environment.clock`。

每条 ActorSkill 的 `actor_entity_id` 必须等于所属 Character/NPC 的 `id`。两类 binding 的 `actor_skill_id` 必须引用同一 actor 的 `skills[].id`；Prepare 还必须引用同槽位、同技能的 Jifa，并满足 `[] / {1} / {1,2}` 的 combine order 约束。

`character_version / inventory_version` 必须与 `11_PROTOCOL_CATALOG.md` 的聚合版本语义一致；golden 命令导致背包、装备或 Item 位置变化时，期望差异必须同时断言两个版本。

`equipment_bindings[].item_instance_id` 的外键目标是 `items[].id`，即 Item Entity 的主键，不是游戏 `instance_id`。槽位必须匹配 quantity=1 Item 的 exact compiled definition，wearer 可引用同实例 Character 或 NPC。

黄金初始态中上述 Character、Room、Exit、NPC 与 Item 的 `lifecycle_state` 必须全部为 `active`。任何专门验证 tombstone 的后置状态必须显式断言 `retired`，不得从缺省值推断。

位置只有一套输入真源：Entity 的 `location_entity_id`、Exit 的 `target_room_id / direction / aliases` 投影，以及 Room 的 `external_exit_boundaries`。黄金用例可另存位置只读断言，但测试框架只能从这些权威字段计算它，不得用它写入或覆盖初始态；两者不一致时必须在执行命令前失败。

黄金用例还必须记录命令输入、期望状态差异、期望事件与允许忽略的展示差异。必做能力的非允许差异必须阻断并保持 `blocked / unverified`；只有包络预先声明的纯展示差异或非必做项可进入包含负责人、依据与复核日期的例外清单。

每次对齐验收必须生成不可变 `compatibility_envelope_id`，绑定 source snapshot、两个 manifest、复合 bundle、golden case 哈希、能力清单、允许差异和负责人。

包络内每项能力只允许 `verified / blocked / unverified`。只有 `verified` 可计入对齐声明；包络外行为不得在报告或发布说明中被推断为已对齐。

首条 `GoldenSkillChain` 必须把 `bahuang-gong` 的 `exert powerup` 与 `baihua-cuoquan` 的 `jifa / prepare / perform cuo` 固定在同一不可变 golden case 或其显式引用中，绑定 `xkx100-skill-combat-v1`、完整初始态、RNG / 时钟、expected diff、事件与 case hash。两段任一缺少来源闭包、exact revision 或非允许差异时，M1-A / M1 保持 `blocked / unverified`。`benlei-shou` 双准备只作为后置用例，不得伪装成首条链的必做通过证据，也不得替代上述候选链。

### 8.1 世界物化与重启幂等

fixture 必须覆盖 world init 连续执行与进程重启；static/spawn 唯一键命中时不得新增 Room、Exit、NPC、Item、`ActorSkill` 或 binding。

测试必须覆盖 Exit direction/alias 与 external boundary 冲突、exact Room revision 不匹配、nested loadout 失败及孤立 combine order 2；任一情况都必须回滚并阻断首发 fixture 启动。

创建 `SpawnMaterialization` 后，测试必须先冻结其整行，再分别执行以下后续变化：

- spawned Entity 移动到其他合法 Room 或 holder。
- spawned NPC 死亡结算，使其已装备 loadout Item 掉落并删除对应 EquipmentBinding；随后再把该 Item 放入合法容器。
- spawned Entity 的 `lifecycle_state` 转为 `retired` tombstone，且 `location_entity_id` 变为 null。
- 受审计的显式 revision migration 在兼容性校验后更新 spawned Entity 的 `blueprint_revision_id`。

每项变化后都必须重启进程并重跑 world init。原 `SpawnMaterialization` 的全部字段和值必须逐列不变；迁移后其 `target_blueprint_revision_id` 仍记录初始 exact revision，移动后也仍记录初始 Room。

已有唯一键必须被解释为该 ordinal 已完成，而不是“当前不在初始位置”或“revision 已变化”。不得生成替代 Entity，不得复活 retired Entity，也不得重复创建 NPC 的技能、Item 或 binding。

这些测试必须证明 INSERT consistency 只验证初始物化事实。后续合法移动、死亡掉落、容器变化、retire 与显式迁移不得被历史记录阻断，也不得反向更新或删除历史记录。

### 8.2 Item 位置、容器与并发

首发必须同时覆盖 Action 服务、PostgreSQL deferred trigger 和协议错误映射。使用当前版本且结构非法时，错误码固定如下：

所有可能改变 Item 位置、数量或 EquipmentBinding 的 ActionDefinition 都必须在 registry 测试中证明 `requires_inventory_version=true`。active Presence 的全部 action 请求都带版本，但 false 动作不得因陈旧背包版本失败。

- 跨实例 location、retired target 或其他非 active target 返回 `ENTITY_LOCATION_INVALID`。
- 目标 Item 的 `container_policy.mode=none`，或 exact `accept_rule_key` 拒绝时返回 `ITEM_CONTAINER_NOT_ALLOWED`。
- bounded 容器直接子项数已达 exact `max_slots` 时返回 `ITEM_CONTAINER_FULL`。
- self containment、放入任一 descendant，或其他会形成 containment cycle 的写入返回 `ITEM_CONTAINER_CYCLE`。

测试必须证明 Room、Character、NPC 与 Item location 都遵守同实例和 active target 矩阵；Item 作为 target 时还必须读取自身 pinned revision 的 exact container policy，不得按 active batch 漂移。

容量并发用例固定一个仅剩一格的 bounded 容器，让携带相同当前 `expected_inventory_version` 的两个请求并发放入不同 Item。只能有一个提交；另一个必须返回 `INVENTORY_VERSION_CONFLICT`，重取 snapshot 后由新用户意图以新版本提交则返回 `ITEM_CONTAINER_FULL`。

环路并发用例让两个 active、同实例 bounded Item 并发互放。无论请求到达顺序，最终只能形成 DAG；陈旧请求先返回 `INVENTORY_VERSION_CONFLICT`，新用户意图使用新版本形成环路时必须返回 `ITEM_CONTAINER_CYCLE`。

还必须覆盖 ancestor chain 在等待行锁期间变化的竞跑。服务按 Entity id 稳定加锁后重读 target、ancestor、容量和 state versions；不能只依赖事务开始前的检查结果。

任一失败都必须原子保留 Item 的 `location_entity_id / state_version`、容器直接子项集合、相关 EquipmentBinding、`character_version` 与 `inventory_version`，且不得发布成功事件或写入声称成功的审计记录。

消耗测试至少覆盖 quantity=2 的部分消耗和 quantity=1 的最终消耗。前者保持同一 active Item、location 与 binding 语义并把 quantity 减一；后者原子删除 binding，把 quantity 置 0、lifecycle 置 retired、location 置 null，并从 inventory snapshot 移除。

两种成功都必须断言 Item `state_version` 及受影响 Character 的两个聚合版本推进，资源/Effect 与 Item 状态同事务提交。故障注入必须证明失败时所有字段和版本不变；若 Item 有 SpawnMaterialization，最终消耗后重启也不得改写记录或重生。

Item 生命周期测试使用冻结时钟覆盖：NPC death/drop 原子创建 30 秒 `LootClaim`；claim 内非领取者被拒绝、恰好到期后公开；多请求并发拾取只有一个赢家。未拾取 NPC loot 在 900 秒策略边界进入保留 identity/history 的 `ItemRetirement`。玩家普通丢弃 Item 在 3600 秒前收到告警并到期退休；重新拾取、进入背包、装备或受保护 policy 会阻止该清理。清理任务重试、与拾取竞跑和进程重启都不得硬删除、重复领取、错误退休或复活死亡 Entity / retired Item。

`xkx100-skill-combat-v1` 及其依赖闭包未实际冻结时，武学/战斗黄金链必须标记 `manual_review` 或 `blocked`，不得计为通过。合成 fixture 只能验证引擎机制，不能替代 XKX100 黄金差分或对齐证据。

本机绝对路径只用于定位候选输入，不能作为验收身份。快照或 manifest 变化必须走显式评审、创建新版本并重新生成差分报告。

## 9. 内容来源责任边界

工程验收只校验来源快照、逐文件哈希、manifest、复合 bundle 与制品依赖是否完整且可复现。

内容许可、权利证明和公开发布法律判断由具体部署者在工程流程之外负责，不属于 M0-M6 或发布门禁。CI、构建和部署不得要求 `content_release_mode`，也不得从来源记录推断权利状态。

## 10. 发布门禁

本节未加限定的“发布候选”指 Public V1 候选；M1-B 的内部候选只执行 V6 明确列出的 M1 范围证据，不得把本节完整清单倒推为 M1 已完成。

发布候选必须同时满足：

- 数据库迁移和回滚演练通过
- 备份恢复演练通过
- 首发纵切及黄金测试通过
- 必做兼容包络项全部为 `verified`，不存在 `manual_review`、`blocked` 或 `unverified`
- 安全扫描无未接受的高风险项
- 协议与内容 schema 版本已记录
- Blueprint/registry 反向依赖闭包、dependency-recompile revisions、compiler contract、compiled hash、registry definition hash、两类 exact dependencies 与只读兼容目录回归全部通过
- 监控、告警和值班处置入口可用
- capacity profile、浏览器矩阵和恢复预算全部达标

发布门禁和必做能力不得用例外改写为通过。仅非必做项的延期处置可记录负责人、风险、补救措施和失效日期，且不得改变门禁结论。

## V6 增量：PublicV1Gate 与 ReleaseManifest

`PublicV1Gate`（`RELEASE-001`）独立于 M0-M6 和 Engine Stage Ex，只验证一个 owner-operated 官方单实例。M1-A / M1-B 是封闭内部步骤，不能自动开启公开注册。通过 gate 前必须完成：

- 7 天封闭试运行、至少 5 名非管理员测试者、至少 20 次核心循环。
- 完整浏览器矩阵、容量与两小时 soak、覆盖账号 / 角色 / 世界拓扑 / 内容批次 / 审计链五个范围的发布级恢复演练。
- S0 / S1 清零；有 workaround、负责人和到期日的受限 S2 例外；S3 可公开记录。
- 社区规则、恢复 / 关闭说明、保留摘要、可用性声明和内容责任确认已发布。
- RecoveryCode 恢复/轮换、账号 `active -> cooling_off -> retired` 生命周期、旧会话与 Presence 撤销以及恢复后重新 enter 的 E2E 证据。
- PlayerBlock、ChannelMute、不可变消息取证、一次申诉、处罚 `effective_at / expires_at`、自批禁止和 30/180/365 天保留清理的 moderation E2E 与审计证据。
- active `ContentReleaseBatch` 与 ReleaseManifest 的机器清单证明可连通的约 30-60 个 Room、10 个以上具功能或敌对行为的 NPC、20 个以上 Item 定义和至少一条武学路径；E2E 证明至少一条可重复 PvE 循环，封闭试运行记录首次游玩约 2-4 小时。计数、行为、时长和 envelope 状态任一缺证都不得通过 gate。
- Public V1 协议 / E2E 必须证明 Character 间只有双方确认的非致命 `Sparring` 可以开始，致命或 involuntary 动作使用既有稳定错误码拒绝；玩家败北产生 `SafeDefeat`，不创建 Character death、不丢失玩家 Item，也不回退不可逆成长。

每次部署必须提交完整 `ReleaseManifest`，至少绑定：代码 commit、`requirements_v6.md` 版本、11-16 合同版本、迁移 head、active `ContentReleaseBatch`、不可变 `SourceSnapshot`、Village / combat compatibility envelopes、黄金 / 差分 / 浏览器 / 容量 / 恢复测试报告。回滚必须协调代码、迁移与内容批次；紧急回滚还要记录原因和受影响批次。计划冷维护提前 24 小时公告，执行 drain、健康检查和证据记录；紧急维护建立 incident 记录。

Public V1 无支付、订阅、付费 Item 或真实货币经济；实例注册模式只能为审计的 `open / paused / invite_only`。初始 superuser 由安全的一次性管理命令创建，不得使用默认凭据。平台必须提供公开 status、maintenance notice、SystemNotice 和统一恢复 / 举报 / 申诉 / 客服入口。

Public V1 H5 E2E 必须覆盖未认证和已认证状态下的公开 status、计划维护窗口、drain 状态、活动 incident、`system.maintenance` / SystemNotice 与恢复通知。进入 drain 后不能新建 enter 或 IC action，已提交终结仍安全收敛；health check、status 投影和 H5 展示不得互相伪造，维护与安全通知不得被玩家屏蔽。
