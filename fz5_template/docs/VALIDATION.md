# 实际验证记录

## 2026-11-20 FZ5D 实机复测

用 Vivado 和 Vitis Classic 2023.1 重建默认 FZ5D 配置，PS 7 GiB、PL 预留 1 GiB。通过 J1 下载，经 J13 的 COM3 采集到 `FZ5_DIAG_END`，结果为 **12 项通过、0 项失败、3 项跳过、6 项待人工验证**。

- GEM3 在 MDIO 地址 4 读到 YT8511 的 ID `0000:010A`。链路状态为 down。网络包收发单独验收。
- eMMC 的旧初始化在 HS200 的 CMD21 调谐阶段失败。诊断改用 8 位兼容模式读第 0 扇区。SD1 初始化使用清零的驱动状态，实际插入的 TF 卡也成功读出第 0 扇区。
- 旧 Block Design 把低有效的 `aux_reset_in` 接到 0，PL 外设保持复位。改为高有效后，AXI GPIO 回环、64 KiB BRAM 读写和高地址 DDR 的 AXI DMA 回环都实测通过。
- JTAG 流程在 FSBL 前启动 PMUFW。SD 启动用的 `BOOT.BIN` 已重新打包。本次实体板验证走 JTAG。

重新布线后的 WNS 为 **5.536 ns**，WHS 为 **0.010 ns**。DRC 有 0 个错误和 4 个 AXI DMA FIFO 的 BRAM 碰撞提示。当前哈希见 [build-manifest.json](build-manifest.json)，原始结果见 [串口日志](../../fz5_vitis/build/2271d2b678ec/uart.log) 和 [测试统计](../../fz5_vitis/build/2271d2b678ec/hardware-result.json)。

## 2026-11-18 构建记录

日期：2026-11-18，工具：Windows / PowerShell 7.6.5 / Vivado 与 Vitis Classic 2023.1。

终端界面使用 Textual 6.12.0。测试选项由独立 Vitis 应用的 `src/test_options.h` 管理。

默认硬件配置 ID 为 `2271d2b678ec4181b5a476009ea00ed0603315ec1b4b310e11ee67c3ffc698f9`。移除硬件配置中的 `TEST_*` 字段后，逐项核对了其余参数。下列 Vivado 实现报告来自原构建目录 `build/3fc54fd1085b/`。

## 已完成

| 检查 | 结果 |
|---|---|
| Kconfig / CLI / TUI / Tcl交接 | 44项通过；覆盖4/8 GiB几何、范围、依赖、非法修改不落盘、特殊字符路径、目录移动、LF/CRLF/BOM、过期配置拒绝、双语命令以及全屏菜单交互 |
| 配置环境 | 使用本机 uv 0.12.10、Python 3.14.7；CLI以本地editable包安装，Kconfiglib内置，uv.lock锁定Textual 6.12.0及终端依赖；setuptools只用于安装/打包 |
| 全屏终端界面 | `uv run fz5-config --lang zh` 在真实Windows终端启动/退出成功；Textual Pilot实际驱动方向键、数值弹窗、布尔开关、保存、退出取消/放弃、预设/撤销、搜索/帮助、语言切换及80×24小窗口 |
| 独立 Tcl 初始化入口 | 实际使用 Vivado 2023.1 运行 `tcl/init_project.tcl`，创建工程/BD/预综合XSA成功；初始化过程中未调用Python |
| 双语 CLI | 无子命令默认进入全屏TUI，menu/menuconfig同样进入TUI；保留get/set/enable/disable等脚本入口；覆盖zh/en/both帮助、语言环境变量、退出码、搜索/说明及JSON |
| 语言与硬件独立 | 同一路径下分别以zh/en/both保存相同配置，JSON和全部生成文件逐字节一致；语言不改变CONFIG_ID |
| CLI打包 | 实际生成 `py3-none-any.whl`，内含中英文catalog和console_scripts入口；已从项目外目录调用安装后的命令 |
| PS DDR 参数比较 | 默认 XSA 的 87 项 DDR 参数与提供的 2023.1 参考 XSA 逐项一致 |
| PS→PL 时钟 | 默认 XSA 的 `pl_clk0` 为 99.999001 MHz，来源为以 33.333 MHz PS 参考时钟为输入的 RPLL |
| FZ5D 默认 | 实际 BD 校验、生成、综合、布局、布线、bitstream、固定平台 XSA |
| FZ5C 4 GiB | 实际 BD 校验、生成工程/预综合 XSA；行地址16位，PS3 GiB/PL1 GiB |
| Minimal | 实际 BD 校验、生成工程/预综合 XSA；无 PL GPIO/BRAM/DMA，无已关闭 PS 外设 |
| Full | 实际 BD 校验、生成工程/预综合 XSA；USB3、DP、RS232 IP/外部端口启用 |
| XSA 配置矩阵核对 | 4 种配置的 PS 开关、PL IP 存在性、DDR 几何符合各自配置 |
| 默认时序 | WNS **5.926 ns**、WHS **0.010 ns**；TNS/THS为0；无无时钟寄存器、无未约束内部端点 |
| 默认 DRC | 0 Error；4条 Warning，见下文 |
| 最终 bitstream 导出 | 0 Error、0 Critical Warning；日志 `docs/evidence/final-export-2026-11-18.log` |
| XSA 导入/软件平台 | 本机 Vitis 实际导入带 bitstream 的 XSA，生成 standalone BSP、FSBL、PMUFW、诊断应用及 system project |
| 诊断 ELF | 实际编译/链接成功；ELF64 / AArch64 / 入口 `0x100000` |
| 独立测试选项 | 复用已验证的 XSA，使用 Vitis 源码目录的 `test_options.h` 重新生成工作区、ELF 和 BOOT.BIN |
| 软件增量更新 | 实际执行 `platform config -updatehw`、BSP 更新、重新编译，并刷新 XSA/ELF 哈希记录 |
| 可选软件分支 | full + 外部回环、minimal 的 `main.c` 分支均使用 AArch64 GCC `-Wall -Wextra -Werror -fsyntax-only` 检查通过；这不是额外完整 BSP/板卡运行验证 |
| BOOT.BIN | Bootgen 2023.1 实际生成，包含 FSBL、PMUFW、bitstream、A53 ELF |
| 主机脚本 | PowerShell 语法解析、Python 编译检查；XSA 内外 bitstream 逐字节比较通过 |

默认利用率：11,619 LUT（9.92%）、16,286 寄存器（6.95%）；完整报告在 `build/3fc54fd1085b/utilization.rpt`。时序和 DRC 完整报告同目录。

## 保留的提示和验证边界

本轮配置入口改为 **Python只编辑配置 → Tcl读取保存后的config初始化工程**。Makefile已移除。`config.py`、`pyproject.toml`、`uv.lock` 和 Tcl 输入采用可移植路径；主流程不依赖 PowerShell。原有 PowerShell 文件保留为 Windows 辅助脚本。跨平台路径/换行检查已通过，但本次没有在 Linux 主机上实际启动 Vivado；Windows 原生 Vivado 初始化已实测。普通 Tcl 交接测试使用本机 Python 的 Tcl 9.0.4，实际工程校验使用 Vivado 自带 Tcl。

最终 DRC 的4条提示均为 AXI DMA 内部 FIFO 的 `REQP-1934/1935`：BRAM `NO_CHANGE` 读写碰撞提示。没有降低规则严重级别或屏蔽 DRC。基础设计已成功生成 bitstream；需要通过实际 DMA 回环，以及将来的压力测试/仿真进一步确认所用数据通路。

Full 配置还有 DP 视频/音频 PLL 与其他外设可能共用的工具提示；本模板提供固定时钟配置，不能把 BD 校验视为已验证 Linux 运行时切换分辨率/音频频率。

4 GiB、Full 和 Minimal 配置验证到 BD 和硬件交接。默认配置完成综合和布局布线，后续实测结果见本页开头。

XDC 在相应端口启用时静态加载。最终 XSA 由原生固定平台描述加实际 bitstream 打包，Vitis 已导入并构建。

