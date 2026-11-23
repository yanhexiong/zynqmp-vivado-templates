# AXU4EV-F Vitis 外设诊断工程

配套 [`../axu4ev_template`](../axu4ev_template/README.md) 的裸机诊断工程（运行在 Cortex-A53 #0；基线验证版本为 **Vitis Classic 2023.1**，亦支持选用其他带 `xsct` 与 `bootgen` 的已安装 Vitis 版本）。  
用于验证在 Vivado 中配置并导出的 Block Design（`.xsa` + `.bit`）在 Vitis 下是否能正常驱动板上的 PS 和 PL 外设。

> **前置条件**：确保 `../axu4ev_template/export/` 下已有带 bitstream 的 `.xsa`（仓库默认已预置一份默认配置导出包，改过硬件后请先在 `axu4ev_template/` 跑完 `bitstream`）。

以下命令均在 **`axu4ev_vitis/` 目录下**执行（Windows / Linux 通用）。

---

## 1. 调整测试项（可选）

代码入口在 `src/main.c`，所有测试开关都在 `src/test_options.h` 里控制：
- `DIAG_TEST_LED`：闪烁底板 LED1 / LED2（MIO39 / MIO40）
- `DIAG_TEST_MEMORY`：低端 DDR 读写 + 高端 DDR 每 GiB 采样检查
- `DIAG_TEST_STORAGE`：QSPI JEDEC ID、eMMC、TF 卡只读第 0 扇区测试（**绝不擦写介质**）
- `DIAG_EXTERNAL_LOOPBACK`：外部 PL 串口回环测试（默认关闭 `0`）
- `DIAG_TIMEOUT_MS`：外设轮询超时时间（默认 `2000` ms）

> 只修改 `src/test_options.h` 时**不需要重跑 Vivado**，直接重新编译 Vitis 工程和 `BOOT.BIN` 即可。

---

## 2. 构建工作区与启动镜像

### 推荐方式：跨平台 Python 构建脚本

```bash
# 查看本机已安装的 Vitis 版本（及是否包含 xsct / bootgen）
python3 scripts/build.py toolchains

# 创建/更新 Vitis 工作区并编译出 axu4ev_diagnostics.elf
python3 scripts/build.py build

# 打包 SD 卡启动镜像 BOOT.BIN（含 FSBL + PMUFW + PL bitstream + 诊断 ELF）
python3 scripts/build.py boot
```

常用可选参数：
- `--hardware <导出目录>`：指定非默认的硬件导出目录（默认为 `../axu4ev_template/export`）
- `--workspace <路径>`：指定自定义 Vitis 工作区路径
- `--tool-version <版本>`：指定已安装的 Vitis 版本（例如 `2023.2`）
- `--vitis-dir <路径>`：直接指定 Vitis 安装根目录

> Windows 下也保留了兼容包装脚本：`pwsh -File scripts/build.ps1 -Action build` / `pwsh -File scripts/build.ps1 -Action boot`。

### 手动方式：已加载 Vitis 环境的原生 XSCT 命令行

```bash
python3 scripts/verify_bundle.py ../axu4ev_template/export
xsct scripts/create_workspace.tcl ../axu4ev_template/export build/my-workspace
```

### 构建输出目录 `build/<配置ID前12位>/`

默认输出在 `build/<配置ID前12位>/`（例如 `build/8900186fcb2c/`）：

| 路径 | 产生时机 | 说明 |
|---|---|---|
| `workspace/` | `build` | Vitis Classic 工作区，可用 Vitis GUI 打开（内含 `axu4ev_platform`、`axu4ev_diagnostics`、`axu4ev_diagnostics_system`）；指定 `--workspace` 时实际路径写入 `build-record.json` |
| `axu4ev_diagnostics.elf` | `build` | 编译好的 A53 裸机诊断程序 |
| `vitis-build.log` | `build` | XSCT 创建/编译工作区的完整日志 |
| `config.json` / `build-record.json` | `build` | 本次构建对应的硬件配置快照与 XSA / ELF 的 SHA256 校验记录 |
| `boot.bif` / `BOOT.BIN` | `boot` | Bootgen 配置文件与最终 SD 卡启动镜像（含 FSBL + PMUFW + bit + ELF） |
| `uart.log` / `jtag.log` / `hardware-result.json` | 上板测试后 | 串口日志、JTAG 下载日志与测试统计 |

---

## 3. 上板运行与串口抓包

开发板有两个独立的 USB 虚拟串口（均为 **115200, 8N1**）：
- **PS 调试控制台**：`J7`（U9 CP2102），对应 UART0（MIO42 RX / MIO43 TX）
- **PL 串口（可选）**：`J8`（U11 CP2102），实测验证板卡上 PL UARTLite 为 AH12 TX、AH11 RX，采用 LVCMOS33

> 请提前插好 TF 卡（如果模板开启了 `PS_SD`），并按开发板手册拨好对应的启动模式拨码。

### 方式一：SD 卡启动（推荐）

1. 将 `build/<配置ID前12位>/BOOT.BIN` 复制到 SD 卡的 FAT 分区根目录。
2. **先开启电脑串口抓取**，再插卡给开发板上电或按复位（Windows 填如 `COM4`，Linux 填如 `/dev/ttyUSB0`）：

```bash
uv run --with pyserial python scripts/serial_test.py --console COM4
```

### 方式二：JTAG 在线下载运行

1. 将开发板拨码设为 **JTAG 模式**，接好 JTAG 线与调试串口并启动 `hw_server`（默认端口 `3121`）。
2. 执行下载并自动采集串口：

```bash
uv run --with pyserial python scripts/serial_test.py --console COM4 --jtag
# 如果电脑同时接了多块板子，用 --cable 指定目标线缆名称或序列号：
uv run --with pyserial python scripts/serial_test.py --console COM4 --jtag --cable '*你的线缆标识*' --server tcp:127.0.0.1:3121
```

> - JTAG 脚本先启动 PMUFW，再配置 PL、运行 FSBL 和诊断 ELF（[AMD JTAG 启动说明](https://docs.amd.com/r/2023.1-English/ug1137-zynq-ultrascale-mpsoc-swdev/Loading-PMU-Firmware-in-JTAG-Boot-Mode)）。
> - 如需指定 Vitis 版本，可加 `--tool-version` 或 `--vitis-dir`。
> - Windows 下也兼容使用：`pwsh -File scripts/Test-Axu4evHardware.ps1 -Port COM4`（加 `-Mode Jtag` 走 JTAG）。

### 测试 PL 串口外部回环（可选）

如果模板开启了 `PL_UART`，把 `src/test_options.h` 中的 `DIAG_EXTERNAL_LOOPBACK` 改为 `1` 并重新编译，然后同时指定 PS 控制台口和 PL 串口跑测试（注意**不要填同一个串口**）：

```bash
uv run --with pyserial python scripts/serial_test.py --console COM4 --pl-echo COM6
```

`serial_test.py` 会把 PL 串口收到的 8 字节测试数据原样回发，板上硬件不需要额外接短接跳线。

---

## 4. 测试项与结果判读

串口输出每条测试都会标明状态：`[PASS]`（通过）、`[FAIL]`（失败）、`[SKIP]`（配置未开启或被 `test_options.h` 跳过）、`[MANUAL]`（需人工观察或进 Linux 进一步确认）。  
最后一行会打印汇总：`AXU4EV_DIAG_END config=... pass=... fail=... skip=... manual=...`。抓取脚本会自动核对 `config` 是否与当前硬件配置一致，并保存 `uart.log` 和 `hardware-result.json`。

| 测试项 | 实际验证内容 | 说明与边界 |
|---|---|---|
| **UART0** | 串口输出诊断日志 | 仅验证 TX 发送；RX 交互需另接终端验证 |
| **PS LED1/2** | MIO39 / MIO40 交替闪烁（高有效） | 闪烁结束后恢复原电平，需肉眼确认（`[MANUAL]`） |
| **PS DDR** | 低端 16 KiB 读写 + 高端每 GiB 采样点写读恢复 | 检查容量与地址混叠，不替代完整内存压测 |
| **I2C0 / EEPROM** | 从 `0x50` 读取 `24LC04` 第 0 块的前 16 字节 | 失败时记录阶段和状态寄存器。NACK 表示器件没有应答 |
| **GEM3 MDIO** | 在地址 `1` 读取 PHY ID 和链路状态，识别 RTL8211F 和 JL2101 | PHY 复位接在 `PS_POR_B`，实际数据收发在 Linux 测试 |
| **QSPI** | 读取 `MT25QU256ABA` JEDEC ID（`20:BB:19`） | 只读 ID，不擦写 Flash |
| **SD0 eMMC / SD1 TF** | eMMC 用 8 位兼容模式，TF 用 SD 驱动，均只读第 0 扇区 | 卡槽稳定报告无卡时显示 `[SKIP]`，失败时记录步骤、命令和状态寄存器 |
| **AXI GPIO** | 32 位 walking-one 内部输出→输入回环 | 验证 PS→PL AXI-Lite 控制通路 |
| **AXI BRAM** | 全 64 KiB 地址特征值写入并回读 | 确认片上 RAM 读写正常 |
| **AXI DMA** | 从 PL 预留高地址 DDR 取 4 KiB 经 AXIS FIFO 回环 | 覆盖 40 位寻址与 `S_AXI_HP0_FPD` 数据通路 |
| **PL UART** | 独立虚拟串口收发 8 字节回显比对 | 需开启 `PL_UART` 和 `DIAG_EXTERNAL_LOOPBACK=1` |
| **USB / DP / RTC** | 输出 `[MANUAL]` 提示（开启 USB0 时会复位 MIO31） | 裸机无协议栈，需进 Linux 验证 |

> **内存运行位置提示**：裸机程序固定链接在低端 DDR `0x00100000`～`0x0fffffff`，不会占用高端 PL 预留区，也会避开 PMU 占用的末尾 1 MiB。

---

## 5. Linux 下进一步验收（可选）

如果后续跑 Linux，把匹配的 `axu4ev-memory.dtsi` 合入设备树并启动系统后，可在板端运行 `scripts/linux_probe.py` 检查设备树保留内存、网口链路与 ping、USB 设备枚举、DP EDID 和 RTC 走时：

```bash
python3 scripts/linux_probe.py --config config.json --peer <对端IP>
```

---

## 6. 目录与脚本清单

- `src/`：`main.c`（诊断主程序）、`test_options.h`（测试开关）、`lscript.ld`（A53 链接脚本，固定在低端 DDR）
- `tests/test_serial_report.py`：串口解析脚本的单元测试（运行 `uv run --with pyserial python -m unittest discover -s tests -v`）

| `scripts/` 文件 | 作用 |
|---|---|
| `scripts/build.py` | 跨平台主构建脚本（`toolchains` 查看已安装 Vitis；`build` 建工作区并编 ELF；`boot` 生成 `BOOT.BIN`） |
| `scripts/build.ps1` | Windows PowerShell 兼容包装脚本（内部转调 `scripts/build.py`） |
| `scripts/verify_bundle.py` | 构建前校验 `export/` 下的配置哈希、DDR 参数、外设开关与 XSA 内外 bitstream 是否一致 |
| `scripts/create_workspace.tcl` | XSCT 脚本，导入 XSA 创建/更新 `axu4ev_platform` 与 `axu4ev_diagnostics` 并编译 |
| `scripts/serial_test.py` | 跨平台 Python 串口抓取器，支持 `--pl-echo` 与 `--jtag` 在线下载 |
| `scripts/Test-Axu4evHardware.ps1` | Windows PowerShell 兼容包装脚本（内部转调 `scripts/serial_test.py`） |
| `scripts/run_jtag.tcl` | XSCT JTAG 下载脚本（复位系统 → 启动 PMUFW → 配置 PL → 运行 FSBL → 下载并运行 ELF） |
| `scripts/linux_probe.py` | 运行在目标板 Linux 下的只读巡检脚本 |
