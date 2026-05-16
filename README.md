# Codex Matrix BPlus

`codex-matrix-bplus` 是 `opencode` 下独立的新架构项目目录。

目标不是替换当前正在跑的主链路，而是为下一代矩阵化主框架提供一个干净的实现空间。

## 项目目标

这套方案按四层结构推进：

1. NAS 总控层
2. 终端代理层
3. 实例运行层
4. 脚本执行层

核心链路：

`NAS 总控 -> 终端代理 -> 实例 -> 脚本`

## 当前范围

当前目录只做以下事情：

- 定义架构分层
- 搭建目录骨架
- 编写模型与接口草案
- 为后续最小原型预留代码位置

当前目录不直接替换以下现有模块：

- `X-Matrix-Bot/`
- `x_matrix_nas/`
- `scrm_monitor/`

## 设计原则

- 总控只做全局调度和持久化
- 终端代理只做本机控制与状态汇聚
- 实例是标准运行单元
- 脚本是执行器，不承担全局调度职责
- 不把页面当成主框架本身

## 目录结构

```text
codex-matrix-bplus/
├─ README.md
├─ docs/
│  └─ architecture.md
├─ nas_control_plane/
│  ├─ README.md
│  ├─ models/
│  │  └─ README.md
│  └─ services/
│     └─ README.md
├─ terminal_agent/
│  ├─ README.md
│  ├─ runtime/
│  │  └─ README.md
│  ├─ adapters/
│  │  └─ README.md
│  ├─ models/
│  │  └─ README.md
│  └─ scripts/
│     └─ README.md
└─ shared/
   ├─ README.md
   └─ protocol/
      └─ README.md
```

## 下一步

下一步优先做 3 件事：

1. 定义终端、实例、任务、脚本运行的数据模型
2. 定义 NAS 与终端之间的协议
3. 先做终端代理最小原型

