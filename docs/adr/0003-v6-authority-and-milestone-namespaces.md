# V6 权威基线与里程碑命名空间

Status: accepted

`requirements_v6.md` 是当前产品需求权威；`requirements_v5.md` 自 V6 生效后保持不可修改的历史基线。活动文档、合同 provenance、自动校验和 ReleaseManifest 必须引用 V6；需要追溯历史时使用单独的 `historical_source_documents` 指针，不得把 V5 混入当前有效来源。

产品需求里程碑 `M0-M6`、需求追踪记录 `MILESTONE-xxx` 与实现路线 `ENGINE-xxx / Engine Stage Ex` 表达不同关系。M0-M6 描述产品结果和验收边界，MILESTONE 记录证据成熟度，Engine Stage 描述可重排的工程依赖。活动文档必须写出所属命名空间，不得使用无上下文的 `Phase x`，也不得把三者合并为一个状态。

这样做是为了让历史文档仍可审计，同时避免历史需求、产品完成度、证据成熟度和工程 readiness 互相覆盖。三套状态可以在同一时点不同，但不得通过编号或单一状态隐式耦合；本 ADR 不保存易陈旧的当前状态，当前值只由 `docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md` 与 `18_IMPLEMENTATION_STATUS.md` 维护。

考虑过的选项：继续把 V5 作为活动文档来源，或把 M0 与 E0 合并为单一阶段。前者会使自动合同门禁验证历史产品边界，后者会把产品证据和工程集成 readiness 错误绑定，因此不采用。
