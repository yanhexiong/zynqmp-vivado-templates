# FZ5 Vitis 外设诊断工程

配套 [`../fz5_template`](../fz5_template/README.md) 的裸机诊断工程（运行在 Cortex-A53 #0；基线验证版本为 **Vitis Classic 2023.1**，亦支持选用其他带 `xsct` 与 `bootgen` 的已安装 Vitis 版本）。  
用于验证 Vivado 导出的 Block Design（`.xsa` + `.bit`）在 Vitis 下是否能正常驱动 FZ5C / FZ5D 的 PS 和 PL 外设。

> **前置条件**：确保 `../fz5_template/export/` 下已有带 bitstream 的 `.xsa`（仓库默认已预置一份 FZ5D 默认配置导出包，改过硬件后请先在 `fz5_template/` 跑完 `bitstream`）。

以下命令均在 **`fz5_vitis/` 目录下**执行（Windows / Linux 通用）。

---

## 1. 调整测试项（可选）

测试逻辑在 `src/main.c`，开关集中在 `src/test_options.h`：
- `DIAG_TEST_LED`：闪烁 RUN 双色灯（MIO43）
- `DIAG_TEST_MEMORY`：低端 DDR 读写 + 高端 DDR 每 GiB 采样检查
- `DIAG_TEST_STORAGE`：QSPI JEDEC ID、eMMC、TF 卡只读第 0 扇区测试（**绝不擦写介质**）
- `DIAG_EXTERNAL_LOOPBACK`：外部串口回环测试（RS485 J11 / PL RS232 J12，默认关闭 `0`）
- `DIAG_TIMEOUT_MS`：外设轮询超时时间（默认 `2000` ms）

> 只修改 `src/test_options.h` 时**无需重跑 Vivado**，直接重编 Vitis 并重新打包 `BOOT.BIN` 即可。

---

## 2. 构建工作区与启动镜像

### 推荐方式：跨平台 Python 构建脚本

```bash
# 查看本机已安装的 Vitis 版本（及是否包含 xsct / bootgen）
python3 scripts/build.py toolchains

# 创建/更新 Vitis 工作区并编译出 fz5_diagnostics.elf
python3 scripts/build.py build

# 打包 SD 卡启动镜像 BOOT.BIN（含 FSBL + PMUFW + PL bitstream + 诊断 ELF）
python3 scripts/build.py boot
```

常用可选参数：
- `--hardware <导出目录>`：指定非默认的硬件导出目录（默认为 `../fz5_template/export`）
- `--workspace <路径>`：指定自定义 Vitis 工作区路径
- `--tool-version <版本>`：指定已安装的 Vitis 版本（例如 `2023.2`）
- `--vitis-dir <路径>`：直接指定 Vitis 安装根目录

> Windows 下也保留了兼容包装脚本：`pwsh -File scripts/build.ps1` / `pwsh -File scripts/build.ps1 -Action boot`。

### 手动方式：已加载 Vitis 环境的原生 XSCT 命令行

```bash
python3 scripts/verify_bundle.py ../fz5_template/export
xsct scripts/create_workspace.tcl ../fz5_template/export build/my-workspace
```

### 构建输出目录 `build/<配置ID前12位>/`

默认输出在 `build/<配置ID前12位>/`（例如 `build/2271d2b678ec/`）：

| 路径 | 产生时机 | 说明 |
|---|---|---|
| `workspace/` | `build` | 默认 Vitis Classic 工作区。指定 `--workspace` 构建时，实际路径写入 `build-record.json` |
| `fz5_diagnostics.elf` | `build` | 编译好的 A53 裸机诊断程序 |
| `vitis-build.log` | `build` | XSCT 创建/编译工作区的完整日志 |
| `config.json` / `build-record.json` | `build` | 本次构建对应的硬件配置快照与 XSA / ELF 的 SHA256 校验记录 |
| `boot.bif` / `BOOT.BIN` | `boot` | Bootgen 配置文件与供 SD 卡启动的完整镜像（含 FSBL + PMUFW + bit + ELF） |
| `uart.log` / `jtag.log` / `hardware-result.json` | 上板测试后 | 串口日志、JTAG 下载日志与测试统计 |

---

## 3. 上板运行与串口抓包

接线与启动准备：
- **J1**：JTAG 接口
- **J13**：调试串口（Micro-USB UART0，**115200, 8N1**）。运行前请先关闭占用该串口的其他终端工具。
- 若启用了 TF 卡测试（`PS_SD`），请提前插入可读的 TF 卡；网口 PHY ID 测试无需插网线。
- 测试程序运行时会初始化外设并关闭外部看门狗，**不要和 Linux 或其他 A53/R5 程序同时跑**。

### 方式一：SD 卡启动（推荐）

1. 按板卡丝印/手册把启动拨码切到 **SD 模式**，将 `build/<配置ID前12位>/BOOT.BIN` 复制到 SD 卡 FAT 分区根目录。
2. 先在电脑开启串口采集，再给板子上电或复位（Windows 填如 `COM7`，Linux 填如 `/dev/ttyUSB0`）：

```bash
uv run --with pyserial python scripts/serial_test.py --console COM7
```

### 方式二：JTAG 在线下载运行

1. 按板卡丝印/手册把启动拨码切到 **JTAG 模式**，接好 **J1** 和 **J13**，并在本机启动 `hw_server`（默认端口 `3121`）。
2. 执行下载并自动采集串口：

```bash
uv run --with pyserial python scripts/serial_test.py --console COM7 --jtag
# 如果电脑同时接了多块开发板，用 --cable 指定目标下载器序列号或名称关键字：
uv run --with pyserial python scripts/serial_test.py --console COM7 --jtag --cable '*210251A08870*' --server tcp:127.0.0.1:3121
```

> - 脚本先启动 PMUFW、配置 PL、运行 FSBL 初始化 DDR，然后下载并运行诊断 ELF（[AMD JTAG 启动说明](https://docs.amd.com/r/2023.1-English/ug1137-zynq-ultrascale-mpsoc-swdev/Loading-PMU-Firmware-in-JTAG-Boot-Mode)）。
> - 省略 `--workspace` 时，JTAG 启动和 `boot` 都自动读取构建记录里的工作区；如需指定 Vitis 版本可加 `--tool-version` 或 `--vitis-dir`。
> - Windows 下也兼容使用：`pwsh -File scripts/Test-Fz5Hardware.ps1 -Port COM7`（加 `-Mode Jtag` 走 JTAG）。

### 外部串口回环测试（可选）

如果开启了 `UART1（RS485）` 或 `PL_RS232`，并且想做自动化回环校验，可将 `src/test_options.h` 中的 `DIAG_EXTERNAL_LOOPBACK` 改为 `1` 后重编：
- **RS485（J11）**：按 A/B/GND 接外部 USB-RS485 适配器（115200 8N1）。可让 `serial_test.py` 自动充当延迟回环对端（默认延迟 15 ms 配合 MIO11 收发切换）：
  ```bash
  uv run --with pyserial python scripts/serial_test.py --console COM7 --pl-echo COM8 --echo-delay-ms 15
  ```
- **PL RS232（J12）**：在 **J12 的 RS232 信号端**短接 TX 与 RX。**切勿把 3.3V TTL 串口适配器直接插到 J12 上**。

---

## 4. 测试项与结果判读

串口输出会按项打印 `[PASS]`、`[FAIL]`、`[SKIP]`、`[MANUAL]`，并在末尾输出 `FZ5_DIAG_END config=... pass=... fail=... skip=... manual=...`。采集脚本会保存 `uart.log` 和 `hardware-result.json`，一旦发现配置 ID 不匹配、`fail > 0` 或超时就会报错退出。

| 测试项 | 自动验证内容 | 说明与边界 |
|---|---|---|
| **UART0 (J13)** | 主机收到完整诊断输出 | 验证 TX 通路；RX 路径需交互终端另测 |
| **RUN 灯 (D46)** | MIO43 翻转 6 次（MIO42 风扇不动） | 肉眼观察 D46 红/黄绿交替闪烁（`[MANUAL]`）；D3 不受控 |
| **PS DDR** | 低端 16 KiB 读写 + 高端每 GiB 采样点写读恢复 | 检查基本读写和 4G/8G 容量混叠，不替代完整内存压测 |
| **I2C1** | 读 EEPROM `0x51` 前 16 字节 | 只读不写；同总线的时钟芯片 `0x76` / PMIC `0x5e` 不修改 |
| **GEM3 MDIO** | MIO30 复位后，读地址 `4` 的 PHY ID 和链路状态 | 识别 YT8511 和 AR8035。包收发与 RGMII 延迟通过 Linux 对端测 |
| **CAN1 (J14)** | 控制器寄存器自检 | 仅验证控制器本身，物理总线需外接带终端电阻的节点对测 |
| **QSPI** | 读 Micron 512 Mbit JEDEC ID | 只读 ID，不擦写 Flash |
| **eMMC / TF (J4)** | eMMC 用 8 位兼容模式，TF 卡用 SD 驱动，均只读第 0 扇区 | TF 卡槽稳定报告无卡时显示 `[SKIP]`。失败时打印步骤、返回码、最后一条命令和控制器寄存器 |
| **PL AXI GPIO** | 32 位 walking-one 内部回环 | 验证 PS→PL AXI-Lite 控制读写 |
| **PL AXI BRAM** | 全 64 KiB 地址特征值写入并回读 | 确认片上 RAM 读写正常 |
| **PL AXI DMA** | 从 PL 预留高地址 DDR 发 4 KiB 经 AXIS FIFO 回写 | 覆盖 40 位寻址、`S_AXI_HP0_FPD`、DMA/AXIS 通路（轮询模式） |
| **RS485 / PL RS232** | 外部发送并校验回显 | 默认 `DIAG_EXTERNAL_LOOPBACK=0` 时输出 `[MANUAL]` |
| **USB / DP / RTC** | 输出 `[MANUAL]` 提示 | 裸机无协议栈，需进 Linux 验收 |

---

## 5. Linux 下进一步验收（可选）

对于 **USB 2.0/3.0**（4 个 Host 口枚举与速率）、**DisplayPort**（EDID 与画面输出）、**千兆网口**（`ping` / `iperf` 与 RGMII 延迟）以及 **RTC 断电走时保持**，需使用基于同一 XSA 构建的 Linux 镜像测试。

把配套 `fz5-memory.dtsi` 合入设备树并启动 Linux 后，可在开发板上运行辅助脚本做只读快速巡检：

```bash
python3 scripts/linux_probe.py --config config.json --peer <对端IP>
```

---

## 6. 目录与脚本清单

- `src/`：`main.c`（诊断主程序）、`test_options.h`（测试开关）、`lscript.ld`（A53 链接脚本，固定在低端 DDR）
- `tests/test_serial_report.py`：串口报告解析单元测试（运行 `uv run --with pyserial python -m unittest discover -s tests -v`）

| `scripts/` 文件 | 作用 |
|---|---|
| `scripts/build.py` | 跨平台主构建脚本（`toolchains` 查看已安装 Vitis；`build` 建工作区并编 ELF；`boot` 生成 `BOOT.BIN`） |
| `scripts/build.ps1` | Windows PowerShell 兼容包装脚本（内部转调 `scripts/build.py`） |
| `scripts/verify_bundle.py` | 构建前校验 `export/` 下的配置哈希、DDR 几何、外设开关与 XSA 内外 bitstream 是否一致 |
| `scripts/create_workspace.tcl` | XSCT 脚本，导入 XSA 创建/更新 `fz5_platform` 与 `fz5_diagnostics` 并编译 |
| `scripts/serial_test.py` | 跨平台串口采集、RS485 延迟回环对端与 `--jtag` 在线下载一体脚本 |
| `scripts/Test-Fz5Hardware.ps1` | Windows PowerShell 兼容包装脚本（内部转调 `scripts/serial_test.py`） |
| `scripts/run_jtag.tcl` | XSCT JTAG 下载脚本（复位系统 → 启动 PMUFW → 配置 PL → 运行 FSBL → 下载并运行 ELF） |
| `scripts/linux_probe.py` | 运行在目标板 Linux 下的只读巡检脚本 |
