# 下一会话最小阅读清单

> 状态：会话交接入口。本文只汇总当前工作起点和最小阅读范围，不创造产品需求、实施合同或状态结论。若本文与权威文档冲突，以 `docs/19_documentation_governance.md` 规定的对应权威来源为准。
>
> 当前交接日期：2026-07-19。

## 1. 开始前检查

新会话先执行：

```powershell
git status --short
git log -5 --oneline
```

当前预期工作树干净；最近五个提交中应包含以下四个实施基线：

| 提交 | 基线 |
| --- | --- |
| `97659ce` | M0 非功能 profile 基线收口 |
| `b4798fb` | 已验证环境与五切片实施计划 |
| `7bd76a3` | M0 工程骨架与可执行合同基线 |
| `e7a3717` | 审计后的正式文档基线 |

若工作树不干净，必须先辨认已有变更并保留用户工作，不得直接还原。

## 2. 最小必读清单

按以下顺序读取，不需要重新全量审核文档：

1. `docs/new_engine/18_IMPLEMENTATION_STATUS.md`
   - 重点：第 2 节当前基线、第 4 节当前状态、第 5 节证据映射和第 6 节变更边界。
   - 用途：确认已经实现、已经验证和仍被阻塞的范围。
2. `plans/m0-e1-tracer-bullets.md`
   - 重点：Architectural decisions 与 Phase 2“E0 受审计内容启动闭环”。
   - 用途：确定下一纵切的范围和验收标准。
3. `docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md`
   - 重点：`CONTENT-001`、`WORLD-001`、`MILESTONE-001`。
   - 用途：在实现完成后按实际证据同步需求状态。
4. `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md`
   - 用途：遵守 Registry、immutable revision、exact dependency、release batch、active batch 与历史 revision 的冻结实施语义。
5. `requirements_v5.md`
   - 只需先精读第 5.4、6.13、6.14 节。
   - 用途：确认 Blueprint、发布边界和实例生效的产品结果。
6. `src/new_mud/apps/content/models.py`
7. `src/new_mud/apps/content/migrations/0001_initial.py`
8. `tests/test_postgres_content_contract.py`
   - 用途：理解现有内容持久模型、数据库约束和测试基线。
9. `contracts/v1/artifacts/` 与 `scripts/verify_m0.py`
   - 用途：复用已冻结的来源制品和现有 M0 合同门禁。

只有在 Phase 2 的实现影响对应关注点时，才继续读取 `docs/new_engine/10_ROADMAP.md`、`16_OPERATIONS_TESTING_CONTRACT.md`、`scripts/generate_source_contracts.py` 和 `tests/test_contracts.py`。无需预先重读全部现行文档。

## 3. 当前工作起点

- M0 机器合同已通过 56,883 项检查，当前没有 profile blocker。
- pytest 共 12 项通过；Ruff、mypy、Django check、迁移漂移和 `pip check` 均通过。
- browser、capacity、recovery 三份 profile 已批准；iOS Safari 保留在首发目标矩阵中。
- `MILESTONE-001` / Engine Stage E0 仍为 `blocked`。
- Phase 2 必须逐一收口三个 E0 阻塞项：
  - 受审计 seed bootstrap。
  - active batch resolver。
  - pinned historical revision resolver。
- 浏览器真实 E2E、容量报告和五业务范围发布恢复仍是后续证据，不得因 M0 profile 获批而提前标记通过。

## 4. 工程边界

- 不修改 `evennia-main/`；它只是 Evennia 6.0.0 本地参考快照。
- 不修改 XKX100 源目录；只能读取并校验来源身份和哈希制品。
- PostgreSQL 凭据只通过临时环境变量使用，不得写入仓库、文档、日志或合同制品。
- 内容授权不属于当前工程范围。
- 不得把结构校验通过等同于 Engine Stage 或需求里程碑完成。
- 状态变化必须同时更新 `18_IMPLEMENTATION_STATUS.md` 和 `17_REQUIREMENTS_TRACEABILITY.md`，并以实际测试证据为准。

## 5. 待补交接元数据

- `18_IMPLEMENTATION_STATUS.md` 第 2 节“当前基线”尚未列出 `b4798fb` 和 `97659ce`；两次提交对应的实施事实已经记录在正文中。
- 被 `.gitignore` 忽略的 `artifacts/reports/pytest-temp-full` 目录仍存在；它不影响 Git、测试或正式证据，可在权限允许时清理。

## 6. 新会话直接指令

> 先检查 Git 状态和最近五个提交，确认其中包含四个实施基线，再读取 `docs/new_engine/NEXT_SESSION_HANDOFF.md` 列出的最小交接入口。从 Phase 2“E0 受审计内容启动闭环”开始实施；保持 iOS Safari 在首发目标矩阵中，按实际证据同步 E0、`CONTENT-001`、`WORLD-001` 和 `MILESTONE-001` 状态，不修改 `evennia-main/` 或 XKX100 源目录，并先补齐实施状态文档中遗漏的两个基线提交身份。
