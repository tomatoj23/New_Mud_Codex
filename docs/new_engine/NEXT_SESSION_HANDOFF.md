# 下一会话最小阅读清单

> 状态：会话交接入口。本文只汇总当前工作起点和最小阅读范围，不创造产品需求、实施合同或状态结论。若本文与权威文档冲突，以 `docs/19_documentation_governance.md` 规定的对应权威来源为准。
>
> 当前交接日期：2026-08-25；状态：`e0_implementation_complete_validation_pending`。

## 1. 开始前检查

新会话先执行：

```powershell
git status --short
git log -5 --oneline
```

当前最前沿是 GitHub Issue #5：完成分层验收、正式状态同步和 E0 提交检查点。最近历史应包含以下实现提交及本 V6 权威前置基线：

| 提交 | 边界 |
| --- | --- |
| 当前 `HEAD` | V6 权威、冻结合同、机器制品、治理与审计前置基线 |
| `9401955` | 并发启动、事务失败矩阵与失败审计 |
| `2eeb682` | 服务器启动生命周期与只读 readiness |
| `c727fba` | 冻结 seed artifact 与受审计 bootstrap |
| `31f6c1a` | Registry exact dependencies |

若工作树不干净，先辨认并保留既有修改；不得还原、清理或混入 Issue #5 之外的工作。

## 2. 最小必读清单

1. `docs/new_engine/18_IMPLEMENTATION_STATUS.md`
   - 确认 `ENGINE-001` 与 `MILESTONE-001` 仍等待 Issue #5 最终证据。
2. `docs/new_engine/PHASE2_CONTENT_STARTUP_WORKLOG.md`
   - 第 1–6 节是 2026-08-23 中间快照；第 7 节记录 Issues #1–#4 完成后的验收前边界。
3. `docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md`
   - 重点：`ENGINE-001`、`CONTENT-001`、`WORLD-001`、`MILESTONE-001` 与 `RELEASE-001`。
4. `plans/m0-e1-tracer-bullets.md`
   - 只处理 Engine Stage E0 / Slice 2 的剩余验收项；E1 尚未开始。
5. `requirements_v6.md` 与 `docs/new_engine/12_REGISTRY_BLUEPRINT_CONTRACT.md`、`16_OPERATIONS_TESTING_CONTRACT.md`
   - 确认 E0、M0 与 PublicV1Gate 的独立边界。

## 3. 当前工作起点

- Issues #1–#4 已完成 E0 / Slice 2 的全部实现项；不应重复实现。
- `ENGINE-001 / Engine Stage E0` 保持 `blocked`，只等待 Issue #5 的当前基线分层验收、证据索引和状态同步。
- `MILESTONE-001 / M0` 保持 `implemented`，等待同一检查点中的最终 clean-baseline checklist。
- `CONTENT-001` 保持 `implemented`：E0 内容启动闭环已实现，完整后台发布服务仍待 M1。
- `WORLD-001` 保持 `specified`：冻结 manifest 和 seed 启动不替代 M1 世界物化与玩法 E2E。
- `RELEASE-001 / PublicV1Gate` 保持 `blocked`；不得把 E0、M0 或 M1-B 当作 Public V1。
- Engine Stage E1 尚未开始。

## 4. Issue #5 可执行顺序

1. 在当前提交上串行运行 `RUN_POSTGRES_TESTS=1` 的 PostgreSQL 合同、服务集成、启动级 E2E 和全量 pytest。
2. 运行 Ruff lint/format、mypy、Django check、迁移漂移、`pip check`、M0 与本地 Markdown 链接检查。
3. 建立包含命令、环境、结果、失败边界和需求/合同引用的证据索引。
4. 只按实际证据同步 `ENGINE-001`、`CONTENT-001`、`WORLD-001` 与 `MILESTONE-001`；不宣称 PublicV1。
5. 对精确 staged diff 执行 Standards / Spec 双轴审查。
6. 形成边界清晰的 Issue #5 提交，回写并关闭 Issue；此后才能开始 E1。

## 5. 工程边界

- 不修改 `evennia-main/` 或 XKX100 来源目录。
- PostgreSQL 凭据不得写入仓库、文档、日志或合同制品。
- 数据库测试和全量 pytest 严格串行，统一使用 `--basetemp artifacts\reports\pytest-temp`。
- 只在证据齐备后改变正式状态；结构检查通过不等于阶段完成。
- 浏览器实际 E2E、容量/soak、五业务范围恢复和公开试运行仍属于后续 M1 或 PublicV1Gate。

## 6. 新会话直接指令

> 确认 V6 权威前置基线与 Issues #1–#4 均在历史中，然后直接认领并完成 Issue #5 的分层验收、证据索引和正式状态同步。保持 `CONTENT-001=implemented`、`WORLD-001=specified` 与 `RELEASE-001=blocked` 的实际边界；Issue #5 关闭前不开始 E1。
