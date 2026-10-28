# SuperMimic启发与本轮边界

已核对[作者项目页](https://supermimic.github.io/) 和[原论文](https://arxiv.org/pdf/2610.28480) （v1，2026-10-20）。其短期可微world-model rollout在末端加critic，critic以imagined lambda return训练，论文以短horizon和push recovery消融检验决策作用。这里仅借鉴有限horizon之外的价值估计思想：本轮先检验真实MuJoCo rolling续跑排序，固定任务gamma=1，若触发则以实际完整剩余成本监督小模型；不复现其world model、BPTT、人体数据规模或硬件结果，不能继承其有效性。
