# AXU4EV-F 可配置 Vivado 工程模板

适用于 **AXU4EV-F**（`xczu4ev-sfvc784-2-i`）的可配置 Vivado 初始化模板（基线验证版本为 **Vivado 2023.1**，亦支持在本地选用其他已安装版本）。  
你可以用自带配置界面裁剪 PS 外设、调节 PL 时钟与共享内存大小，一键生成干净的 Vivado 工程和 Block Design（BD），并导出 `.bit` / `.xsa` 交给旁边的 [`axu4ev_vitis`](../axu4ev_vitis/README.md) 进行上板外设驱动验证。

> **开箱即用**：本目录 `export/` 已附带默认配置编译好的 `axu4ev_system.bit` 与 `axu4ev_system.xsa`。如果暂不需要改动硬件配置，可直接前往 [`../axu4ev_vitis`](../axu4ev_vitis/README.md) 编译软件与 `BOOT.BIN`。

---

## 快速上手（Windows / Linux 通用）

以下命令均在 **`axu4ev_template/` 目录下**执行。

### 1. 配置硬件参数

首次运行同步虚拟环境并启动蓝底全屏配置界面：

```bash
uv sync
uv run axu4ev-config --lang zh
```

界面操作（支持键盘和鼠标，效果与键位详见 [docs/UI.md](docs/UI.md)）：
- `↑` / `↓`：移动光标
- `Enter`：进入子菜单或修改数值
- `空格` / `y` / `n`：开启或关闭选项
- `F2` / `Ctrl+S`：保存并生成配置（`F3` 加载预设，`F4` 切换中/英/双语，`/` 搜索，`F1` 帮助，`F10` 退出）

如果习惯用命令行脚本修改，也可以直接运行子命令：

```bash
uv run axu4ev-config list                             # 查看当前所有配置项
uv run axu4ev-config defconfig --profile minimal      # 加载预设（可选 axu4ev / minimal）
uv run axu4ev-config set PL_RESERVED_MB=512           # 修改参数（改后会自动校验并重新生成）
uv run axu4ev-config disable PS_DP PL_UART            # 关闭指定外设
uv run axu4ev-config generate                         # 根据 .config 重新生成导出文件
uv run axu4ev-config validate                         # 校验当前配置是否合法
```

> **测试独立配置而不覆盖当前 `.config`**：可用 `--config` 和 `--out` 指定独立路径：
> ```bash
> uv run axu4ev-config --config build/minimal/.config --out build/minimal/generated defconfig --profile minimal
> ```

保存后会把以下 4 个文件写到 `generated/`（供 Vivado 和软件工程读取，不要手动编辑）：
- `config.tcl`：Vivado Tcl 读取的配置脚本
- `config.json`：完整参数及内存/外设地址表（其中的 `CONFIG_ID` 前 12 位决定本次构建目录名）
- `axu4ev_config.h`：给 Vitis 测试代码用的 C 头文件（宏前缀 `AXU4EV_`）
- `axu4ev-memory.dtsi`：给 Linux 设备树用的 `reserved-memory` 片段

---

### 2. 生成 Vivado 工程与 Bitstream / XSA

#### 方式一：使用跨平台 Python 入口（推荐，自动查找工具链）

```bash
# 查看本机已安装的 Vivado 版本
python3 scripts/axu4ev.py toolchains

# 仅生成 Vivado 工程、BD 与预综合 XSA
python3 scripts/axu4ev.py project

# 完整跑完综合、布局布线、生成比特流并发布到 export/
python3 scripts/axu4ev.py bitstream

# 使用本机其他已安装版本（例如 2024.1）
python3 scripts/axu4ev.py project --tool-version 2024.1
# 或手动指定 Vivado 安装根目录
python3 scripts/axu4ev.py bitstream --vivado-dir /opt/Xilinx/Vivado/2023.1

# 使用前面单独生成的独立配置目录
python3 scripts/axu4ev.py project --config-dir build/minimal/generated

# 验证 minimal 等预设也能成功建工程
python3 scripts/axu4ev.py matrix
```

- 常用可选参数：`--tool-version <版本>`、`--vivado-dir <路径>`、`--config-dir <目录>`、`--strict-version`（强制要求 2023.1）。

#### 方式二：在 Vivado GUI 或已加载环境的终端运行

- **Vivado GUI Tcl Console**（`cd` 到 `axu4ev_template` 后执行）：
  ```tcl
  source tcl/init_project.tcl
  ```
- **已加载 Vivado 环境的终端批处理**（例如 Linux 已 `source settings64.sh`）：
  ```bash
  vivado -mode batch -source tcl/init_project.tcl
  # 如需使用其他配置目录（例如前面单独生成的 minimal）：
  vivado -mode batch -source tcl/build.tcl -tclargs project build/minimal/generated/config.tcl
  # 跑完整 bitstream 流程：
  vivado -mode batch -source tcl/build.tcl -tclargs bitstream
  ```

> **重要提示**：
> - 如果曾手动修改 `.config`，请先运行 `uv run axu4ev-config generate`，否则 Tcl 一致性校验会拒绝建工程。
> - 基线验证版本为 **Vivado 2023.1**。使用其他版本时，Tcl 流程会打印版本提示并在 `create_bd.tcl` 中自动按当前目录匹配 IP 版本；若需禁止跨版本运行，请设 `ZYNQMP_STRICT_VERSION=1` 或传 `--strict-version`。
> - **打开工程后怎么看 Block Design？** `init_project.tcl` 生成完 BD 后不会自动弹出框图标签页。用 Vivado 打开 `build/<CONFIG_ID前12位>/project/axu4ev.xpr` 后，在左侧 **Flow Navigator → IP INTEGRATOR** 点击 **Open Block Design**（或在 **Sources** 窗口展开 `axu4ev_system_wrapper` 后双击 `axu4ev_system.bd`）。
> - **二次开发建议**：不要直接修改 `build/` 下生成出来的包装代码；扩展自己的 PL 逻辑请修改 `tcl/create_bd.tcl` 并添加自己的 RTL/约束文件。

---

## 构建输出目录说明

模板按 `generated/config.json` 中 `CONFIG_ID` 的前 12 位隔离每次构建，修改配置后不会覆盖旧工程。

### `build/<配置ID前12位>/`（例如默认配置 `build/8900186fcb2c/`）

| 路径 | 产生时机 | 用途说明 |
|---|---|---|
| `project/axu4ev.xpr` | `project` | 生成的 Vivado 工程主文件，可直接用 Vivado GUI 打开 |
| `project/axu4ev.srcs/sources_1/bd/axu4ev_system/axu4ev_system.bd` | `project` | 工程内部真实的 Block Design 文件 |
| `contract/` | `project` | 本次建工程时锁定拷贝的 `config.tcl`、`config.json`、`axu4ev_config.h`、`axu4ev-memory.dtsi` |
| `axu4ev_pre_synth.xsa` | `project` | 预综合硬件平台描述（**不含 bitstream**，仅用于检查 BD/地址导出） |
| `axu4ev_system.bit` | `bitstream` | 布局布线后生成的 FPGA 比特流文件 |
| `axu4ev_system.xsa` | `bitstream` | 带 bitstream 的完整 XSA 硬件平台文件 |

### 模板根目录 `bd/` 与 `export/`

- `bd/`：默认配置初始化时同步保存的 BD 快照（`axu4ev_system.bd`、`axu4ev_system_wrapper.v` 和 `axu4ev_system.tcl`）。传入 `--config-dir` 跑独立配置时快照放在 `build/<id>/bd/`，不会覆盖此处。
- `export/`：跑完 `bitstream` 后更新的正式交付目录，包含 `axu4ev_system.bit`、`axu4ev_system.xsa`、`config.json`、`config.tcl`、`axu4ev_config.h`、`axu4ev-memory.dtsi` 和 `config_id.txt`。`../axu4ev_vitis` 默认从这里读硬件包。

---

## 内存规划（重要）

AXU4EV-F 只有一组 **PS 侧 64 位 DDR4（共 4 GiB）**，**没有独立 PL DDR**。  
配置里的 `PL_RESERVED_MB`（默认 1024 MiB，要求 64 MiB 对齐，范围 0～2048 MiB）是指从 PS 高地址 DDR 末尾划出一块区域专供 PL 侧 DMA/AXI Master 使用。

| 地址范围 | 容量 | 用途说明 |
|---|---:|---|
| `0x000000000`–`0x07fffffff` | 2 GiB | PS 低端 DDR（末尾 1 MiB `0x7ff00000`–`0x7fffffff` 由 PMU 占用，测试与链接脚本需避开） |
| `0x800000000`–`0x83fffffff` | 1 GiB | PS 高端 DDR（默认配置） |
| `0x840000000`–`0x87fffffff` | 1 GiB | PL DMA 预留池（默认配置） |

**使用注意：**
1. **地址空洞**：低 2 GiB 和高 2 GiB 之间隔着外设和 PCIe 映射区，不能当成连续 4 GiB 物理地址访问。
2. **译码窗口不等于物理容量**：HP0 在 BD 中的高端译码窗口虽然有 32 GiB，但板上实际 DDR 只到 `0x87fffffff`。
3. **软件约定**：`PL_RESERVED_MB` 只是给软件分配看的约定，硬件上没有 AXI 防火墙隔离。跑 Linux 时记得把 `generated/axu4ev-memory.dtsi` 合入设备树，用 `no-map` 防止内核把 DMA 池分出去。

---

## 默认 Block Design 与板级外设

### BD 拓扑与 PL 地址映射

默认配置下，PS 通过 `M_AXI_HPM0_FPD` 经 SmartConnect 挂接 4 个 PL 外设（时钟来自 PS `pl_clk0`，默认 100 MHz，可在 50～200 MHz 间配置）；AXI DMA 通过 `MM2S → AXIS FIFO → S2MM` 回环，经另一个 SmartConnect 走 40 位地址接入 `S_AXI_HP0_FPD`：

| PL 地址 | 容量 | IP 模块 | 说明 |
|---|---:|---|---|
| `0xA0000000` | 64 KiB | AXI GPIO | 通道 1 输出内部直连通道 2 输入，用于验证 PS→PL 控制通路 |
| `0xA0010000` | 64 KiB | AXI BRAM | 64 KiB 片上 RAM，用于整块读写测试 |
| `0xA0020000` | 64 KiB | AXI DMA | 轮询模式，64-bit 数据宽度，40-bit 寻址访问高地址 DDR |
| `0xA0030000` | 64 KiB | AXI UARTLite | 可选，引出到底板独立 USB 虚拟串口 |

### 板上外设与引脚速查

| 外设 | 引脚 / 连接位置 | 注意事项 |
|---|---|---|
| 调试串口 UART0 | `J7`（U9 CP2102），MIO42(RX) / MIO43(TX) | 固定保留作为控制台，115200 8N1 |
| PL 串口 UARTLite | `J8`（U11 CP2102），RX `AH11` / TX `AH12` | 实测板使用 `LVCMOS33`，与 PS 串口是**两个独立 USB 口** |
| PS LED1 / LED2 | MIO39 / MIO40 | 高电平点亮 |
| I2C0 | MIO34 / MIO35 | 挂有 `24LC04` EEPROM（块地址 `0x50`/`0x51`）和 `LM75` 温度传感器 |
| 千兆网口 GEM3 | MIO64..77，RTL8211F（MDIO 地址 `1`） | PHY 复位接在全局 `PS_POR_B`，没有单独的复位 MIO |
| QSPI Flash | MIO0..6，Single x4（MT25QU256ABA） | 256 Mbit，JEDEC ID `20:BB:19` |
| eMMC（SD0） | MIO13..23，8 位（MTFC8GAKAJCN-4M） | 8 GB，复位脚 MIO23（低有效） |
| TF 卡（SD1） | MIO46..51，卡检测 MIO45 | — |
| USB 2.0 / 3.0 | ULPI MIO52..63 + GTR Lane1（26 MHz） | 复位脚 `USB_RESET_N` 在 MIO31（低有效） |
| DisplayPort | AUX MIO27..30 + GTR Lane2/3（27 MHz） | 需进 Linux 接显示器验证 |

> 关闭某个 PS 外设只会禁用对应的控制器与 MIO/GTR 复用，不会切断板卡供电。

---

## 目录与脚本清单

### 根目录与配置

- `Kconfig` / `configs/` / `.config`：配置项定义、预设方案（`axu4ev_defconfig`、`minimal_defconfig`）与当前配置
- `axu4ev_config/` / `config.py`：跨平台双语配置界面（Textual TUI）与 CLI 包入口
- `board/ps_config.tcl`：Zynq UltraScale+ PS 参数（DDR 时序、MIO、时钟等）
- `constraints/axu4ev_uart.xdc`：PL UART 引脚约束（仅在开启 `PL_UART` 时加载）
- `docs/`：[界面说明](docs/UI.md) · [板级资料核对](docs/board-profile.md) · [构建状态](docs/build-status.md) · [验证记录](docs/VALIDATION.md)
- `tests/test_configuration.py`：配置与 Tcl 交接单元测试（运行 `uv run python -m unittest discover -s tests -v` 或 `python3 scripts/axu4ev.py check`）

### `tcl/`（Vivado 构建脚本）

| 文件 | 作用 |
|---|---|
| `tcl/init_project.tcl` | **Vivado 初始化入口**，在 GUI Tcl Console 或批处理运行，创建工程和 BD |
| `tcl/build.tcl` | **批处理构建入口**，支持 `-tclargs project`（只建工程）或 `-tclargs bitstream`（综合/实现/出 bit 并发布到 `export/`） |
| `tcl/project_lib.tcl` | 工程初始化核心流程（版本检查/提示、PS 配置、建 BD、生成 wrapper、导出快照与预综合 XSA） |
| `tcl/create_bd.tcl` | 根据 `cfg` 数组动态搭建 Block Design 并分配 AXI 地址（自定义 PL 逻辑改这里） |
| `tcl/config_io.tcl` | 读取 `config.tcl` 并校验 `.config` 与导出文件是否同步 |

### `scripts/`（辅助脚本）

| 文件 | 作用 |
|---|---|
| `scripts/configure.py` | Kconfig 解析、参数校验及生成 `config.tcl` / `config.json` / `axu4ev_config.h` / `axu4ev-memory.dtsi` |
| `scripts/axu4ev.py` | 跨平台一站式入口（支持 `toolchains` / `defconfig` / `menuconfig` / `generate` / `project` / `bitstream` / `matrix` / `check` 及 `--tool-version`） |
| `scripts/toolchain.ps1` | Windows PowerShell 工具链环境兼容辅助脚本（调用跨平台探测逻辑） |
| `scripts/vendor/` | 内置的 `kconfiglib.py` 及许可证文件 |
