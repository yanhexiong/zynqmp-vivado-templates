# FZ5 可配置 Vivado 工程模板

适用于 **EdgeBoard FZ5C（4 GiB）** 与 **FZ5D（8 GiB）** 的可配置 Vivado 初始化模板（基线验证版本为 **Vivado 2023.1**，亦支持在本地选用其他已安装版本）。  
默认对应 FZ5D、8 GiB DDR4、`xczu5ev-sfvc784-1-i`（可在菜单中切换为 FZ5C 或 `-2` 速度等级，请以芯片丝印为准）。

你可以使用内置配置界面裁剪 PS 外设、调节 PL 时钟与共享内存划分，一键生成 Vivado 工程和 Block Design（BD），并导出 `.bit` / `.xsa` 交给旁边的 [`fz5_vitis`](../fz5_vitis/README.md) 进行上板外设驱动验证。

> **开箱即用**：本目录 `export/` 已附带默认 FZ5D 配置编译好的 `fz5_system.bit` 与 `fz5_system.xsa`。如果暂不需要改动硬件配置，可直接前往 [`../fz5_vitis`](../fz5_vitis/README.md) 编译软件与 `BOOT.BIN`。

---

## 快速上手（Windows / Linux 通用）

以下命令均在 **`fz5_template/` 目录下**执行。

### 1. 配置硬件参数

首次运行同步虚拟环境并启动蓝底全屏配置界面：

```bash
uv sync
uv run fz5-config --lang zh
```

界面操作（支持键盘与鼠标，详细说明见 [docs/UI.md](docs/UI.md)）：
- `↑` / `↓`：移动光标
- `Enter`：进入分组或修改数值
- `空格` / `y` / `n`：开关选项
- `F2` / `Ctrl+S`：保存并生成配置（`F3` 加载预设，`F4` 切换中/英/双语，`/` 搜索，`F1` 帮助，`F10` 退出）

也支持非交互命令行（`--lang zh|en|both` 指定语言，`--json` 输出 JSON）：

```bash
uv run fz5-config profiles                           # 查看预设：fz5d / fz5c / minimal / full
uv run fz5-config defconfig --profile fz5c           # 切换到 FZ5C 4 GiB 预设
uv run fz5-config set PL_RESERVED_MB=2048 PS_USB0=n  # 一次修改多个参数并校验
uv run fz5-config enable PS_GEM3                     # 启用指定开关
uv run fz5-config search 内存                         # 搜索中英文选项
uv run fz5-config get PL_RESERVED_MB                 # 读取单个值
uv run fz5-config generate                           # 手改 .config 后同步生成输出文件
uv run fz5-config validate                           # 校验配置合法性
```

> **测试多套配置而不覆盖当前 `.config`**：可以用 `--config` 和 `--out` 指定独立路径：
> ```bash
> uv run fz5-config --config configs/my-board.config --out generated/my-board defconfig --profile fz5d
> ```

保存后会同步更新 `generated/` 下的 4 个交接文件（勿手改）：
- `config.tcl`：Vivado Tcl 读取的配置脚本
- `config.json`：完整参数及内存/外设地址表（其中的 `CONFIG_ID` 前 12 位决定本次构建目录名）
- `fz5_config.h`：给 Vitis 测试代码用的 C 头文件（宏前缀 `FZ5_`）
- `fz5-memory.dtsi`：给 Linux 设备树用的 `reserved-memory` 片段

---

### 2. 生成 Vivado 工程与 Bitstream / XSA

#### 方式一：使用跨平台 Python 入口（推荐，自动查找工具链）

```bash
# 查看本机已安装的 Vivado 版本
python3 scripts/fz5.py toolchains

# 仅初始化 Vivado 工程、BD 与预综合 XSA
python3 scripts/fz5.py project

# 完整跑完综合、布局布线、生成比特流并发布到 export/
python3 scripts/fz5.py bitstream

# 使用本机其他已安装版本（例如 2024.1）
python3 scripts/fz5.py project --tool-version 2024.1
# 或手动指定 Vivado 安装根目录
python3 scripts/fz5.py bitstream --vivado-dir /opt/Xilinx/Vivado/2023.1

# 使用前面单独生成的独立配置目录
python3 scripts/fz5.py project --config-dir generated/my-board

# 批量验证 fz5c / minimal / full 多套预设都能成功建工程
python3 scripts/fz5.py matrix
```

- 常用可选参数：`--tool-version <版本>`、`--vivado-dir <路径>`、`--config-dir <目录>`、`--strict-version`（强制要求 2023.1）。
- Windows 下亦兼容：`pwsh -File scripts/fz5.ps1 -Action project|bitstream|matrix`。

#### 方式二：在 Vivado GUI 或已加载环境的终端运行

- **Vivado GUI Tcl Console**（先 `cd` 到 `fz5_template` 或把相对路径改全）：
  ```tcl
  source tcl/init_project.tcl
  ```
- **已加载 Vivado 环境的终端批处理**（例如 Linux 已 `source settings64.sh`）：
  ```bash
  vivado -mode batch -source tcl/init_project.tcl
  # 或指定独立配置：
  vivado -mode batch -source tcl/init_project.tcl -tclargs generated/my-board/config.tcl
  # 跑完整 bitstream 流程：
  vivado -mode batch -source tcl/build.tcl -tclargs bitstream
  ```

> **重要提示**：
> - 如果曾手动编辑过 `.config`，请先运行 `uv run fz5-config generate`，否则 Tcl 一致性校验会拒绝建工程。
> - 基线验证版本为 **Vivado 2023.1**。使用其他版本时，Tcl 流程会打印版本提示并在 `create_bd.tcl` 中自动按当前目录匹配 IP 版本；若需禁止跨版本运行，请设 `ZYNQMP_STRICT_VERSION=1` 或传 `--strict-version`。
> - **打开工程后怎么看 Block Design？** `init_project.tcl` 生成完 BD 后不会自动弹出框图标签页。用 Vivado 打开 `build/<CONFIG_ID前12位>/project/fz5.xpr` 后，在左侧 **Flow Navigator → IP INTEGRATOR** 点击 **Open Block Design**（或在 **Sources** 窗口展开 `fz5_system_wrapper` 双击 `fz5_system.bd`）。
> - **二次开发建议**：不要直接修改 `build/` 下的生成文件；扩展自定义 PL 逻辑请修改 `tcl/create_bd.tcl` 并添加自己的 RTL/约束文件。

---

## 构建输出目录说明

模板按 `generated/config.json` 中 `CONFIG_ID` 的前 12 位隔离每次构建，修改配置不会覆盖旧工程。

### `build/<配置ID前12位>/`（例如默认配置 `build/2271d2b678ec/`）

| 路径 | 产生时机 | 用途说明 |
|---|---|---|
| `project/fz5.xpr` | `project` | 生成的 Vivado 工程主文件，可直接用 Vivado GUI 打开 |
| `project/fz5.srcs/sources_1/bd/fz5_system/fz5_system.bd` | `project` | 工程内部真实的 Block Design 文件 |
| `contract/` | `project` | 本次建工程时锁定拷贝的 `config.tcl`、`config.json`、`fz5_config.h`、`fz5-memory.dtsi` |
| `fz5_pre_synth.xsa` | `project` | 预综合硬件平台描述（**不含 bitstream**） |
| `fz5_routed.dcp` | `bitstream` | 布局布线后的 Vivado 检查点，方便复查时序/路径 |
| `timing_summary.rpt` / `utilization.rpt` / `drc.rpt` | `bitstream` | 时序、资源利用率与 DRC 报告 |
| `fz5_system.bit` | `bitstream` | 最终生成的 FPGA 比特流 |
| `fz5_system.xsa` | `bitstream` | 已打包进 bitstream 的完整 XSA 硬件平台文件 |

### 模板根目录 `bd/` 与 `export/`

- `bd/`：默认配置初始化时同步保存的 BD 快照（`fz5_system.bd`、`fz5_system_wrapper.v` 和 `fz5_system.tcl`）。传入 `--config-dir` 跑独立配置时快照保存在 `build/<id>/bd/`，不会覆盖此处。
- `export/`：跑完 `bitstream` 后更新的正式交付目录，包含 `fz5_system.bit`、`fz5_system.xsa`、`config.json`、`config.tcl`、`fz5_config.h`、`fz5-memory.dtsi` 和 `config_id.txt`。`../fz5_vitis` 默认读取此目录。

---

## 内存规划（重要）

FZ5 只有一组 **PS 侧 64 位 DDR4**（FZ5D 为 8 GiB，FZ5C 为 4 GiB），**没有独立 PL DDR**。  
配置中的 `PL_RESERVED_MB`（要求 64 MiB 对齐，FZ5D 支持 0～6144 MiB，FZ5C 支持 0～2048 MiB）表示从 PS 高端 DDR 末尾划给 PL DMA/AXI Master 使用的区域，低 2 GiB 始终留给 PS。

默认 **FZ5D（8 GiB）** 划分如下：

| 地址范围 | 容量 | 用途说明 |
|---|---:|---|
| `0x000000000`–`0x07fffffff` | 2 GiB | PS 低端 DDR（末尾 1 MiB 由 PMU 保留） |
| `0x800000000`–`0x93fffffff` | 5 GiB | PS 高端 DDR |
| `0x940000000`–`0x97fffffff` | 1 GiB | PL DMA 预留池 |

**使用注意：**
1. **地址空洞**：低 2 GiB 与高端 DDR 之间存在外设地址空洞，不能按连续物理内存访问。
2. **软件约定**：预留容量只是一份软件分工约定，硬件上没有 AXI 访问隔离（BD 中 `HP0` 仍能看到完整 DDR 窗口）。Linux 集成时请把 `generated/fz5-memory.dtsi` 合入设备树，利用 `no-map` 防止内核占用该区域。
3. **DDR 频率说明**：模板沿用参考工程已验证的 PS DDR 参数（64 位、4×x16、单 rank，实际控制器时钟约 600 MHz / 1200 MT/s；文档里写的 2400 Mbps 是颗粒/器件速度档位）。

---

## 默认 Block Design 与板级外设

### BD 拓扑与 PL 地址映射

默认配置下，PS 通过 `M_AXI_HPM0_FPD` 经 SmartConnect 挂载 PL 外设；AXI DMA 的 `MM2S → AXIS FIFO → S2MM` 经另一个 SmartConnect 走 40 位地址接入 `S_AXI_HP0_FPD`。  
PL 逻辑时钟来自 PS 的 `pl_clk0`（由 33.333 MHz `PS_REF_CLK` 经 RPLL 分频，默认 100 MHz，可在菜单「板卡与共享 DDR4 → PS→PL 时钟」调节 50～200 MHz；注意它不同于原理图上的 25 MHz `PL_CLK_25M`）。

| PL 地址 | 容量 | IP 模块 | 说明 |
|---|---:|---|---|
| `0xA0000000` | 64 KiB | AXI GPIO | 32 位内部输出直连输入，测试控制通路 |
| `0xA0010000` | 64 KiB | AXI BRAM | 64 KiB 片上 RAM |
| `0xA0020000` | 64 KiB | AXI DMA | 轮询模式，64-bit 数据宽度，40-bit 寻址 |
| `0xA0030000` | 64 KiB | AXI UARTLite | 可选（`PL_RS232`），连接到 J12 |

### 板上外设与踩坑提醒

| 外设 | 连接 / 引脚 | 常见坑点与说明 |
|---|---|---|
| **JTAG / 调试串口** | **`J1` 是 JTAG**，**`J13` 是 UART0**（MIO26/27） | 部分早年文档把 JTAG 错写成 J13；UART0 固定保留，115200 8N1 |
| **RUN 灯 / 风扇** | **D46 绿灯在 MIO43/K19**，**风扇在 MIO42/L18** | D46 是红绿双色灯（D3 是配置完成灯）；**切勿把 MIO42 当 LED 翻转** |
| **RS485（UART1）** | `J11`，MIO8/9，收发方向 MIO11 | 可选；外部测试需发收之间留出方向切换时间 |
| **PL RS232** | `J12`，RX `AE15` / TX `AB14`（LVCMOS33） | 经过板载 **RS232 电平芯片**，**严禁直接接 3.3V TTL 串口线** |
| **I2C1** | MIO24/25，EEPROM 地址 `0x51` | 同总线还有时钟芯片 `0x76`、PMIC `0x5e`，自检只读 EEPROM |
| **CAN1** | `J14`，MIO28/29 | 诊断只做控制器寄存器自检，物理总线需外接节点 |
| **千兆网口 GEM3** | `J17`，MIO64..77，复位 MIO30 | AR8035 PHY 的 `4` 是 **MDIO 地址**（不是 I2C 地址） |
| **QSPI / eMMC / TF** | QSPI: MIO0..5；eMMC: MIO13..23（8位）；TF: `J4` MIO46..51 | TF 卡检测在 MIO45，未启用 WP；只读验证不擦写 |
| **USB 2.0 / 3.0** | ULPI MIO52..63 + GTR1（26 MHz），复位 MIO39/40 | 默认关闭（`full` 预设开启），建议进 Linux 测枚举与速率 |
| **DisplayPort** | `J6`，MIO34..37 + GTR2/3（27 MHz） | 默认关闭（`full` 预设开启），需接显示器在 Linux 验证 |

> 关闭外设只会禁用对应 PS 控制器/复用引脚或移除 PL IP，不会切断板上供电（测试代码也不会翻转 MIO31/32 电源使能脚）。HDMI / MIPI / VCU 本模板暂未实例化。

---

## 目录与脚本清单

### 根目录与配置

- `Kconfig` / `configs/` / `.config`：配置项定义、4 套预设（`fz5d` / `fz5c` / `minimal` / `full`）与当前配置
- `fz5_config/` / `config.py`：跨平台双语配置界面（Textual TUI）与 CLI 包入口
- `board/`：`ps_config.tcl` 及从参考 XSA 提取的 `reference_ddr_8g.json`
- `constraints/fz5.xdc`：PL RS232 引脚约束（仅开启 `PL_RS232` 时加载）
- `docs/`：[界面说明](docs/UI.md) · [硬件资料核对与勘误](docs/SOURCES.md) · [验证记录](docs/VALIDATION.md)
- `tests/`：配置编辑、TUI 与 Tcl 交接单元测试（运行 `uv run python -m unittest discover -s tests -v` 或 `python3 scripts/fz5.py check`）

### `tcl/`（Vivado 构建脚本）

| 文件 | 作用 |
|---|---|
| `tcl/init_project.tcl` | **Vivado 初始化入口**，在 GUI Tcl Console 或批处理运行，创建工程和 BD |
| `tcl/build.tcl` | **批处理构建入口**，支持 `-tclargs project`（只建工程）或 `-tclargs bitstream`（综合/布局布线并导出） |
| `tcl/project_lib.tcl` | 工程初始化核心流程（版本检查/提示、PS 配置、建 BD、生成 wrapper、导出快照与预综合 XSA） |
| `tcl/create_bd.tcl` | 根据 `cfg` 数组动态搭建 Block Design 并分配 AXI 地址（自定义 PL 逻辑改这里） |
| `tcl/config_io.tcl` | 读取 `config.tcl` 并校验 `.config` 与导出文件是否同步 |
| `tcl/export_routed.tcl` | 对布线后设计检查时序/DRC、写 `.dcp`/`.bit`，并调用 `package_xsa.py` 生成最终 XSA |

### `scripts/`（辅助与打包脚本）

| 文件 | 作用 |
|---|---|
| `scripts/configure.py` | Kconfig 解析、参数校验及生成 `config.tcl` / `config.json` / `fz5_config.h` / `fz5-memory.dtsi` |
| `scripts/fz5.py` | 跨平台一站式入口（支持 `toolchains` / `defconfig` / `menuconfig` / `generate` / `project` / `bitstream` / `matrix` / `check` 及 `--tool-version`） |
| `scripts/fz5.ps1` / `scripts/check_matrix.ps1` | Windows PowerShell 兼容包装脚本（内部转调 `scripts/fz5.py`） |
| `scripts/toolchain.ps1` | Windows PowerShell 工具链环境兼容辅助脚本（调用跨平台探测逻辑） |
| `scripts/package_xsa.py` | 把布线生成的 `.bit` 打包进预综合 `.xsa` 并更新元信息，同时发布到 `export/` |
| `scripts/vendor/` | 内置的 `kconfiglib.py`、`menuconfig.py` 及许可证文件 |
