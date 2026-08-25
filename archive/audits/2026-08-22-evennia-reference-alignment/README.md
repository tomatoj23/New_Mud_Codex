# Evennia 参考边界对齐审查记录

> 历史声明：本文记录 2026-08-22 的文档对齐快照，不代表当前权威。截至当前审查，产品需求权威为根目录 `requirements_v6.md`；`requirements_v5.md` 仅用于历史追溯。

## 1. 审查目的

根据 2026-08-22 对本地 Evennia 6.0.0 快照的判断，复核现行项目文档是否把“版本维护状态”“传统架构特征”和“对 New_Mud 的适配性”混为一谈，并直接修正文档中的过度表述、陈旧导航和借鉴边界。

本记录只描述文档审查与修改，不创造产品需求、实施合同或代码状态。

## 2. 范围与权威边界

- 覆盖 46 份项目自有现行 Markdown 文档：根目录说明、V5 需求、术语、合同、计划、`docs/00-20`、`docs/new_engine/00-18` 与 `NEXT_SESSION_HANDOFF.md`。
- `archive/` 中的历史需求和历史审计只作对照，不改写历史结论。
- `evennia-main/` 是 Evennia 6.0.0 固定参考快照，本次只读源码和文档，未修改其内容。
- 当时产品结果以 `requirements_v5.md` 为准；协议和实施机制以 `docs/new_engine/11-16` 为准；需求追踪以 `17` 为准；当前实现证据以 `18` 为准；Evennia 来源事实和适配性评估以 `docs/00-18`、`docs/20` 及本地快照为准。当前产品结果改以 `requirements_v6.md` 为准。

## 3. 统一结论

Evennia 6.0 是“现代维护中的传统架构”：没有整体落后，在传统多协议 MUD 场景仍成熟；但 Portal/Server/AMP、默认文本 WebClient、动态 Typeclass、任意 pickle 状态和 Lockstring 不适合 New_Mud 的 Web-first、PC/移动 H5 双端、结构化协议和强 schema 目标。

应复用的是领域语义、处理顺序、hook、不变量和边界问题清单，不是 Twisted/AMP、进程形状、动态状态注入或源码组织。命令生命周期、移动 Hook、Prototype、帮助、频道和会话问题域仍保留参考价值。

## 4. 本次修改

| 文档 | 修改内容 |
| --- | --- |
| `README.md` | 增加最小文档入口，链接需求、治理、实施状态和 Evennia 评估。 |
| `docs/00_analysis_completion_record.md` | 纳入 `docs/20`，记录复核日期与结论，移除已过时的“下一步建议”并改为当前阅读路径。 |
| `docs/01_typeclass_system.md` | 区分动态换类/proxy/pickle 的适配问题与“版本落后”，明确只借鉴语义。 |
| `docs/04_command_system.md` | 保留 Telnet 文本模型的成熟性，明确结构化输入是 New_Mud 的协议选择。 |
| `docs/08_server_architecture.md` | 增加“现代维护、目标不同”的限定，统一 PC/移动 H5 表述并回链评估。 |
| `docs/13_web_layer.md` | 补入默认 WebClient 的本地源码证据，区分陈旧客户端工程与 Django Web 整合能力。 |
| `docs/16_architecture_overview.md` | 增加总判断，修正首发端表述，限定“历史包袱”为项目适配成本。 |
| `docs/19_documentation_governance.md` | 将 `docs/20` 纳入分析层、权威矩阵、导航、映射和已核验状态。 |
| `docs/20_evennia_modernity_assessment.md` | 建立现代性与参考边界评估入口，并统一为“PC/移动 H5 双端”和“默认客户端陈旧”的精确表述。 |
| `docs/new_engine/00_README.md` | 将“照抄”改为复用语义/顺序/不变量，补充 `docs/20` 导航。 |
| `docs/new_engine/01_BORROW_REWRITE_MATRIX.md` | 重命名借鉴层级，收紧 File help、Portal/Server 和最终原则的措辞。 |
| `docs/new_engine/02_ARCHITECTURE.md` | 说明 ASGI 选择来自产品和一致性边界，不是因 Evennia 无维护；修正架构口号。 |
| `docs/new_engine/18_IMPLEMENTATION_STATUS.md` | 将 Evennia 来源分析范围更新为 `00-18` 与 `20`，并校准当前 M0 检查数；不改变实现状态。 |
| `docs/new_engine/NEXT_SESSION_HANDOFF.md` | 更新交接日期、已知工作树、M0 检查数、Evennia 条件阅读边界和进入 Phase 2 的前置条件。 |
| `requirements_v5.md` | 当时将分析/治理同步范围从 `docs/00-19` 扩展为 `docs/00-20` 的历史工作树变更；V5 当前保持冻结，不再继续修改。 |

## 5. 已复核但无需实质修改

以下文档已按主题、术语和上述统一结论复核，现有内容与当前边界一致，本轮未做实质改写：

- `docs/02_object_system.md`、`03_account_system.md`、`05_script_system.md`、`06_lock_system.md`、`07_comm_system.md`、`09_session_management.md`
- `docs/10_prototype_system.md`、`11_help_system.md`、`12_utils.md`、`14_database_design.md`、`15_contrib_highlights.md`
- `docs/17_mudlib_interface.md`、`18_mudlib_converter.md`
- `docs/new_engine/03` 至 `17`
- `UBIQUITOUS_LANGUAGE.md`、`contracts/v1/README.md`、`plans/m0-e1-tracer-bullets.md`

这些文档仍受 `docs/19_documentation_governance.md` 的权威边界和术语规则约束。

## 6. 未改变的产品与工程语义

- 没有把 Evennia 作为运行时依赖，也没有修改 `evennia-main/`。
- 没有改变 Django/DRF/Channels/Daphne/PostgreSQL、ASGI、单实例单写者、WebSocket/REST、Blueprint、MUDLib、会话状态机或冻结合同语义。
- 没有把文档审查结果伪装成实现里程碑；`docs/new_engine/18` 的阻塞状态保持不变。

## 7. 验证记录

- 全局扫描 `照抄`、`移动端优先`、`docs/00-18`、`docs/00-19`、过时/陈旧表述并逐项判断。
- `git diff --check`：通过。
- 本次变更文档的本地 Markdown 链接检查：通过。
- `scripts/verify_m0.py`：通过，共 56,904 项检查；M0 合同基线为 `READY`。
- 本记录未新增 Markdown 链接；其中的代码样式路径均以仓库根目录为基准。审计记录自身不参与 M0 活动文档扫描。

本次仅留下工作树修改，未创建 Git 提交。
