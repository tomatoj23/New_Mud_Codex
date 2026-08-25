# Engine documentation authority audit — 2026-08-23

审查范围：`docs/new_engine/00_README.md`–`19_V6_CONTRACT_DIFFERENCES.md`、`NEXT_SESSION_HANDOFF.md`、`PHASE2_CONTENT_STARTUP_WORKLOG.md`、`plans/m0-e1-tracer-bullets.md`，以及 `contracts/v1/` 下 README、catalogs、schemas、profiles、artifacts、reports。

权威依据：`requirements_v6.md`；`docs/19_documentation_governance.md`；`CONTEXT.md`；`UBIQUITOUS_LANGUAGE.md`；`contracts/v1/README.md`；`docs/new_engine/11_PROTOCOL_CATALOG.md`–`16_OPERATIONS_TESTING_CONTRACT.md`（实施合同）；`17_REQUIREMENTS_TRACEABILITY.md` 与 `18_IMPLEMENTATION_STATUS.md`（追踪/状态）。V5 仅按权威文档允许的历史对照使用。

验证动作（只读）：运行 `.venv\\Scripts\\python.exe scripts/verify_m0.py`，结果 `M0 CONTRACT STRUCTURE PASSED (56981 checks)`；运行 `pytest -q`，结果 `16 passed, 3 skipped`（3 个 PostgreSQL 合同测试因未设置 `RUN_POSTGRES_TESTS=1` 跳过）；核对 JSON profile/report/artifact 的哈希、枚举和计数；扫描 `docs/new_engine` 与计划中的本地引用。

## Findings

### Blocking

无。机器合同结构门禁通过，未发现会使当前 V6/11–16 合同互相无法解析的 catalog/schema 阻断。

### Major

1. **恢复错误码与冻结协议冲突** — [docs/new_engine/03_RUNTIME_SESSIONS.md:203](../../../docs/new_engine/03_RUNTIME_SESSIONS.md:203) 写明“其他 AuthSession”调用 `presence.recover` 返回 `CHARACTER_OCCUPIED`。冻结协议要求：`presence.recover` 只查找当前 AuthSession 自有租约；找不到时统一返回 `PRESENCE_RECOVERY_UNAVAILABLE`，不得泄露其他会话占用（[11_PROTOCOL_CATALOG.md:219](../../../docs/new_engine/11_PROTOCOL_CATALOG.md:219)、[13_SESSION_AUTH_STATE_MACHINE.md:381](../../../docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md:381)）。`CHARACTER_OCCUPIED` 仅适用于普通 `presence.enter`（11:178–179、13:290）。建议将 03:203 改为 `PRESENCE_RECOVERY_UNAVAILABLE`，并明确仅显式 `presence.takeover` 进入占用提示/接管流程。

2. **实施状态账本滞后于 E0 Slice 2 中间实现** — [docs/new_engine/18_IMPLEMENTATION_STATUS.md:115-117](../../../docs/new_engine/18_IMPLEMENTATION_STATUS.md:115) 断言 seed bootstrap、active resolver、pinned historical resolver “尚未实现”。当前工作记录 [PHASE2_CONTENT_STARTUP_WORKLOG.md:32-61](../../../docs/new_engine/PHASE2_CONTENT_STARTUP_WORKLOG.md:32) 已记录 `startup.py` 的事务创建路径和 `resolver.py` 的 `resolve_active/resolve_pinned`，且 [PHASE2_CONTENT_STARTUP_WORKLOG.md:79-86](../../../docs/new_engine/PHASE2_CONTENT_STARTUP_WORKLOG.md:79) 将相应项列为 `partial`/`implemented_unverified`，不是不存在。建议 18:115–117 改为“中间实现存在但真实冻结制品加载、Registry exact dependency、服务集成、并发/审计/readiness 验收未完成”，并同步 17 的证据说明；继续保持 `ENGINE-001=blocked`，不要把中间实现提升为完成。

3. **恢复报告 SHA-256 在状态账本中错误** — [docs/new_engine/18_IMPLEMENTATION_STATUS.md:96](../../../docs/new_engine/18_IMPLEMENTATION_STATUS.md:96) 写 `7be50190…e8748f82`。实际 [contracts/v1/reports/m0-recovery-latest.json](../../../contracts/v1/reports/m0-recovery-latest.json) SHA-256 为 `50335d0cc36d507bcbc5a674f8a0ed6d5b1360dc5d1a4fc2a6a43c5899a3aac9`，且同一值已冻结于 [contracts/v1/profiles/recovery-budget.json:41](../../../contracts/v1/profiles/recovery-budget.json:41)；`verify_m0.py` 只验证 profile/report 一致，未捕获该叙述性账本漂移。建议以实际文件哈希和 profile 值更新 18:96，并在状态更新流程加入文档哈希交叉检查。

4. **交接文档保留已被复核否定的“parent dependency 未重跑”状态** — [docs/new_engine/NEXT_SESSION_HANDOFF.md:57,76](../../../docs/new_engine/NEXT_SESSION_HANDOFF.md:57) 仍称最后一次 parent exact dependency 修改“尚未重新验证/尚未重新运行测试”。同文件 71–75 已记录最新 `pytest 16 passed, 3 skipped` 及 Slice 2 中间实现；工作记录 [PHASE2_CONTENT_STARTUP_WORKLOG.md:7,93](../../../docs/new_engine/PHASE2_CONTENT_STARTUP_WORKLOG.md:7) 明确 2026-08-23 已运行 `tests/test_content_startup.py` 并 `7 passed`。建议删除/改写 57、76 为“已验证 7 passed，但 PostgreSQL/服务集成/启动 E2E/全量门禁仍未完成”，并保留 E0 `blocked`。

5. **同一工作记录内部测试结论互相矛盾** — [docs/new_engine/PHASE2_CONTENT_STARTUP_WORKLOG.md:7](../../../docs/new_engine/PHASE2_CONTENT_STARTUP_WORKLOG.md:7) 与 :93 说明测试已 `7 passed`，但 :75 仍说第七个场景“尚未重新运行、不是七项当前均通过”。这会误导下一会话和状态同步。建议以 7 passed 的复核证据为当前事实，删除旧的 :75 开发时快照或明确标为历史（同时保留 :81–87 的 partial/pending 结论）。

### Minor

6. **历史需求引用未使用归档路径，形成断链/可搜索误导** — [docs/new_engine/18_IMPLEMENTATION_STATUS.md:33](../../../docs/new_engine/18_IMPLEMENTATION_STATUS.md:33) 写“将 `requirements_v1.md` 到 `requirements_v4.md` 移入 `archive/requirements/`”，但正文只给根文件名；根目录不存在这些文件，实际入口是 `archive/requirements/requirements_v1.md`–`requirements_v4.md`（见 [archive/requirements/README.md](../../../archive/requirements/README.md)）。建议将四个文件写成可点击的归档路径，并在历史审计记录中使用同一路径。

7. **概念页对绑定型成功交付的表述过宽** — [docs/new_engine/03_RUNTIME_SESSIONS.md:90](../../../docs/new_engine/03_RUNTIME_SESSIONS.md:90) 说 `presence.enter/takeover/session.resume` 的“成功终结结果”都直接交付新 ticket 和完整 snapshot。冻结协议 11:149–155、4.1 规定跨连接终结重放可能是 `delivery.status=resume_required`（可返回安全 ticket 但省略历史 snapshot），`superseded` 则不返回 ticket/snapshot；只有当前连接 `bound` 首次交付才交付完整 snapshot。建议补充“首次 bound 成功”限定并指向 11:4.1，避免概念页覆盖实施合同。

8. **转换 profile 示例把绝对本机路径写成配置字段，未标注其非身份性质** — [docs/new_engine/09_MUDLIB_CONVERTER.md:284-293](../../../docs/new_engine/09_MUDLIB_CONVERTER.md:284) 的 `root: D:/My_Projects/xkx100-20201118` 容易被当作可复现身份。权威 V6 7.2/7.2.1 与实施合同 16:142-146、16:258-260 要求以不可变 `source_snapshot_id`/逐文件哈希作为身份，本机绝对路径只能定位候选输入。建议将字段改名/注释为 `source_locator`，并明确必须解析并校验 `source_snapshot.json`，不能把路径写入 manifest、ReleaseManifest 或验收身份。

9. **工作记录状态词未与追踪索引的枚举对齐（仅过程文档）** — [docs/new_engine/PHASE2_CONTENT_STARTUP_WORKLOG.md:81-85](../../../docs/new_engine/PHASE2_CONTENT_STARTUP_WORKLOG.md:81) 使用 `partial`、`implemented_unverified`，而 17 的正式需求状态枚举仅允许 `specified / implemented / verified / blocked / retired`（[17_REQUIREMENTS_TRACEABILITY.md:8-14](../../../docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md:8)）。过程快照可以使用细粒度词，但应显式标注“非需求状态”并映射到 `implemented`/`blocked`，否则下游工具可能误解析。建议在表头加注或改用 `evidence_state` 字段。

## Cross-checks with no findings

- `contracts/v1/catalogs/*.json` 的 protocol、error、state、registry 值与各自 11/12/13/08 文档逐向核对；`scripts/verify_m0.py` 56981 项通过。
- `browser-matrix.json`、`capacity-profile.json`、`recovery-budget.json` 的批准状态、目标矩阵、容量阈值、RPO/RTO、五个恢复范围与 16/requirements_v6 对齐；`tested_versions`、容量/soak 和发布级恢复仍为空/不具 gate 资格，未发现夸大为 PublicV1 证据。
- `source_snapshot.json`（14018 文件）、world manifest（5 roots/44 deps）、skill manifest（14 roots/11 deps）及 composite bundle 的同一 `source_snapshot_id`、计数和哈希与 09/14/16/V6 对齐；bundle 当前 `alignment_status=blocked`，未被文档宣称为 verified。
- `contracts/v1` 的 `historical_source_documents=["requirements_v5.md"]` 是显式历史对照且根文件存在，不构成 V5 当前权威回退。
- 已逐篇检查 `docs/new_engine/00-10` 概念/路线、11-16 冻结合同、17/18 追踪状态、19 差异、交接/工作记录和 `plans/m0-e1-tracer-bullets.md`；除上述条目外，未发现旧里程碑编号、PublicV1Gate/M1-A/M1-B 分层、术语（User/GameAccount/ConnectionSession/AuthSession/Presence/Blueprint/ConditionDefinition/EffectInstance 等）或合同字段与权威文档的新增冲突。

## 修复与复核（2026-08-23）

本次主审查已处理上述发现，且没有改变 V6 产品结果、11–16 冻结合同或正式需求状态：

1. `03_RUNTIME_SESSIONS.md` 将跨 AuthSession 的 `presence.recover` 错误改为 `PRESENCE_RECOVERY_UNAVAILABLE`，并限定只有普通 `presence.enter` 使用 `CHARACTER_OCCUPIED`；同时补充 `delivery.status=bound`、`resume_required` 和 `superseded` 的交付边界，回链 `11_PROTOCOL_CATALOG.md` 第 4.1 节。
2. `18_IMPLEMENTATION_STATUS.md` 将 E0 Slice 2 的 bootstrap/resolver 记录为“已有中间实现、尚未完成真实制品加载/Registry/服务集成/并发/审计/readiness 验收”，保持 `ENGINE-001 / Engine Stage E0=blocked`。
3. 状态账本的恢复报告 SHA-256 已更新为报告文件和 `contracts/v1/profiles/recovery-budget.json` 共同冻结的 `50335d0cc36d507bcbc5a674f8a0ed6d5b1360dc5d1a4fc2a6a43c5899a3aac9`。
4. `NEXT_SESSION_HANDOFF.md` 与 `PHASE2_CONTENT_STARTUP_WORKLOG.md` 已统一记录 2026-08-23 `tests/test_content_startup.py` 的 `7 passed`，并明确这不等于 E0 完成。
5. 历史需求链接已改为 `archive/requirements/requirements_v1.md`–`requirements_v4.md`；归档入口和旧需求头部均明确 V5 只是当时基线、V6 是当前权威。
6. `09_MUDLIB_CONVERTER.md` 将示例路径标为 `source_locator`，并明确只有 `source_snapshot.json` 的 ID 与哈希构成来源身份。
7. 工作记录表将 `partial` / `implemented_unverified` 标注为非 17 的正式需求状态；`docs/19_documentation_governance.md` 与 V6 第十七章补入差异清单、过程记录、计划和机器合同的分层说明。

复核命令：

- `.venv\\Scripts\\python.exe scripts\\verify_m0.py` → `M0 CONTRACT STRUCTURE PASSED (56981 checks)`，`M0 CONTRACT BASELINE: READY`。
- `.venv\\Scripts\\python.exe -m pytest -q` → `16 passed, 3 skipped`；跳过项为未设置 `RUN_POSTGRES_TESTS=1` 的 PostgreSQL 合同测试。
- `git diff --check` → 通过。
- 审查对象 Markdown（根目录、`docs/`、`plans/`、`contracts/`、`archive/`，不含本报告与 `evennia-main/`）共 69 份；连同本报告共 70 份。本地 Markdown 链接检查 0 断链、0 结构 H1 问题（`AGENTS.md` 是用户提供的指令文件，刻意不要求 Markdown H1）。
