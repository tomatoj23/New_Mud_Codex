# 下一会话最小阅读清单

> 状态：会话交接入口。本文只汇总当前工作起点和最小阅读范围，不创造产品需求、实施合同或状态结论。若本文与权威文档冲突，以 `docs/19_documentation_governance.md` 规定的对应权威来源为准。
>
> 当前交接日期：2026-08-25；状态：`e0_verified_e1_not_started`。

## 1. 开始前检查

新会话先执行：

```powershell
git status --short
git log -5 --oneline
```

Engine Stage E0 / Slice 2 已由 Issues #1–#5 完成实现和验收。最近历史应包含 Issue #5 检查点、V6 权威基线及以下实现提交：

| 提交 | 边界 |
| --- | --- |
| 当前 `HEAD` | Issue #5 分层证据、状态同步与 E0 关闭检查点 |
| `d14ce67` | V6 权威、冻结合同、机器制品、治理与审计前置基线 |
| `9401955` | 并发启动、事务失败矩阵与失败审计 |
| `2eeb682` | 服务器启动生命周期与只读 readiness |
| `c727fba` | 冻结 seed artifact 与受审计 bootstrap |
| `31f6c1a` | Registry exact dependencies |

若工作树不干净，先辨认并保留既有修改；不得还原、清理或混入 Issue #5 之外的工作。

## 2. 最小必读清单

1. `docs/new_engine/18_IMPLEMENTATION_STATUS.md`
   - 确认 `ENGINE-001` 与 `MILESTONE-001` 已为 `verified`，且 `RELEASE-001` 仍为 `blocked`。
2. `docs/new_engine/PHASE2_CONTENT_STARTUP_WORKLOG.md`
   - 第 1–6 节是 2026-08-23 中间快照，第 7 节是验收前边界，第 8 节是 Issue #5 的最终证据索引。
3. `docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md`
   - 重点：`ENGINE-001`、`CONTENT-001`、`WORLD-001`、`MILESTONE-001` 与 `RELEASE-001`。
4. `plans/m0-e1-tracer-bullets.md`
   - E0 两个切片已关闭；E1 尚未开始，后续必须使用独立 ticket。
5. `requirements_v6.md` 与 `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md`、`16_OPERATIONS_TESTING_CONTRACT.md`
   - 确认 E0、M0 与 PublicV1Gate 的独立边界。

## 3. 当前工作起点

- Issues #1–#5 已完成 E0 / Slice 2 的实现、分层验收、证据索引与状态同步；不应重复实现。
- `ENGINE-001 / Engine Stage E0` 与 `MILESTONE-001 / M0` 均为 `verified`。
- `CONTENT-001` 保持 `implemented`：E0 内容启动闭环已实现，完整后台发布服务仍待 M1。
- `WORLD-001` 保持 `specified`：冻结 manifest 和 seed 启动不替代 M1 世界物化与玩法 E2E。
- `RELEASE-001 / PublicV1Gate` 保持 `blocked`；不得把 E0、M0 或 M1-B 当作 Public V1。
- Engine Stage E1 尚未开始。

## 4. 下一步边界

1. 确认 Issue #5 已关闭且工作树干净，不重做 E0。
2. 从 `plans/m0-e1-tracer-bullets.md` 选择 E1 的第一个独立 ticket；先读取 `08`、`11`、`13`、`15`、`16` 的认证与连接边界。
3. E1 继续按 ticket 做 test-first 实现和独立双轴审查，不把 PublicV1Gate 的浏览器、容量、恢复或公开运营证据提前计入 M1。

## 5. 工程边界

- 不修改 `evennia-main/` 或 XKX100 来源目录。
- PostgreSQL 凭据不得写入仓库、文档、日志或合同制品。
- 数据库测试和全量 pytest 严格串行，统一使用 `--basetemp artifacts\reports\pytest-temp`。
- 只在证据齐备后改变正式状态；结构检查通过不等于阶段完成。
- 浏览器实际 E2E、容量/soak、五业务范围恢复和公开试运行仍属于后续 M1 或 PublicV1Gate。

## 6. 新会话直接指令

> 确认 Issue #5 的 E0 检查点已在历史且工作树干净，再从独立 ticket 开始 E1。保持 `CONTENT-001=implemented`、`WORLD-001=specified` 与 `RELEASE-001=blocked` 的实际边界，不把 E1 或 M1 内部候选误写为 Public V1。
