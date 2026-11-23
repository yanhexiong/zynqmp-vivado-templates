# 实际验证记录

## 2026-11-20 AXU4EV-F 实机复测

默认配置按 PS 3 GiB、PL 预留 1 GiB 运行。JTAG 下载后从 J7 的 PS 串口（COM4）抓到完整日志，共 **10 项通过、1 项失败、0 项跳过、6 项待人工验证**。PS UART 另用主机发出的四个字节验证了 RX。J8 的复测记录见下文。

- 修正 Block Design 的辅助复位极性并重建。PL AXI GPIO、64 KiB BRAM 读写和高地址 DDR 的 4 KiB DMA 回环均通过。
- GEM3 地址 1 实测读出 JL2101 的 `937C:4032`。新版诊断识别 JL2101 和 RTL8211F。这次链路为 down，数据收发待验收。[JL2101 PHY 驱动补丁](https://lists.openwall.net/netdev/2026/10/16/443)
- DDR 抽查、QSPI JEDEC ID、eMMC 和插入的 TF 卡通过。eMMC 用 8 位兼容模式只读第 0 扇区。
- I2C0 EEPROM `0x50` 在地址阶段返回 NACK。I2C0 用 100 kHz、50 kHz 及 GPIO 地址探测，在 `0x48..0x57` 都未得到应答。原厂示例采用的 I2C1（MIO24/25）上，同一地址范围也没有应答。定位到具体器件或电平转换电路还需要测量板上信号。

Vivado 重建后的 WNS 为 **5.459 ns**，WHS 为 **0.010 ns**，DRC 仍有 4 条 DMA FIFO BRAM 提示。实体板验证使用 JTAG，SD 启动用的 `BOOT.BIN` 已重新打包。[串口日志](../../axu4ev_vitis/build/8900186fcb2c/uart.log) · [测试统计](../../axu4ev_vitis/build/8900186fcb2c/hardware-result.json)

### PL 串口 J8 实机复测

JTAG 边界扫描确认本次实测板的 J8 接收信号接到 `AH11`。用 `AH11` 接收、`AH12` 发送及 `LVCMOS33` 重建完整工程后，开启 Vitis 外部回环。AXI UARTLite 以 115200 8N1 发送 `55 AA 12 34 5A A5 87 78`，PC 在 COM5 收到并原样回送，FPGA 校验全部 8 字节通过。默认导出的 bitstream、XSA 和 SD 启动镜像已更新。本次上板使用 JTAG。[J8 实测记录](../../axu4ev_vitis/build/8900186fcb2c/pl-uart-j8-result.json) · [本次 Vivado 工程](../build/j8-ah/build/8900186fcb2c/project/axu4ev.xpr)

## 2026-11-19 构建记录

日期：2026-11-19。工具：Windows、PowerShell 7、uv 0.12.10、Python 3.14.7、Vivado / Vitis Classic 2023.1、Textual 6.12.0。

默认硬件配置 ID 为 `8900186fcb2c342e9dba1ea204bd0c96b749bf33d68881f1d9a3ba1770ac81f8`。移除硬件配置中的 `TEST_*` 字段后，逐项核对了其余参数。下列 Vivado 实现报告来自原构建目录 `build/6a8d054f23be/`。

## 已完成

| 检查 | 结果 |
|---|---|
| 配置与全屏界面 | 7项自动检查通过：4GiB物理内存与32GiB AXI译码窗口区分、默认1GiB预留、范围/对齐/依赖、0预留禁用DMA、完整中英翻译、真实TUI键盘交互及保存、语言不影响生成文件、小窗口搜索/帮助和错误回退 |
| 实际终端 | 安装后的 `uv run axu4ev-config --lang zh` 在Windows交互终端启动/退出成功，默认进入蓝底全屏界面；英文/双语由参数或F4选择 |
| CLI打包 | 实际生成 `axu4ev_config-0.3.0-py3-none-any.whl`；独立Python包名使两个板卡CLI可分开安装；uv.lock锁定终端依赖 |
| Python/Tcl分工 | Python只保存配置；实际原生Vivado初始化从config.tcl读取配置，生成工程/BD及硬件交接 |
| 默认工程 | `build/6a8d054f23be/project/axu4ev.xpr`，BD校验、生成、综合、布局布线、bitstream均成功 |
| 默认时序 | WNS **5.915ns**，WHS **0.010ns**；TNS/THS为0，unrouted nets为0 |
| 最终DRC | 0 Error、0 Critical Warning；4条DMA内部BRAM碰撞提示，见下文 |
| 管脚 | 原构建用了 AB2 和 G5。实测板的管脚已改为 AH12 和 AH11，见上方 J8 复测 |
| 原生XSA | 实际 `write_hw_platform -fixed -include_bit` 成功；zip完整，内外bitstream逐字节一致 |
| 最小配置 | 独立ID `5be3c4b73c70`，实际BD校验/预综合XSA成功；HWH核对可选PS控制器关闭、GPIO/BRAM/DMA/UART等PL模块不存在、UART0保留；未对最小配置布局布线 |
| 默认配置保留 | 根.config及generated/export仍为默认配置；根bd快照与默认工程BD哈希相同，未被minimal覆盖 |
| Vitis工作区 | 实际导入最终带bitstream的XSA，updatehw并重新生成standalone BSP、FSBL、PMUFW、axu4ev_diagnostics及system project |
| ELF | 编译/链接成功，ELF64 / AArch64，入口0x100000；含诊断起止标记及匹配配置ID |
| 独立测试选项 | 复用已验证的 XSA，使用 Vitis 源码目录的 `test_options.h` 重新生成工作区、ELF 和 BOOT.BIN |
| 可选软件分支 | 外部PL UART回显打开、minimal关闭外设两个分支，用AArch64 GCC `-Wall -Wextra -Werror -fsyntax-only`通过；这不是这两种配置的完整BSP/上板验证 |
| BOOT.BIN | Bootgen实际成功生成；含FSBL、PMUFW、PL bitstream、A53诊断ELF |
| 串口抓取器 | 4 项模拟串口检查通过，覆盖有效结果与 PL 回显、固件跳过回显、配置 ID 不一致和外设测试失败 |
| 辅助脚本 | PowerShell 7语法解析、Python编译检查通过；最终bundle校验通过，build-record记录XSA和ELF哈希 |

默认Vivado实现及最小配置的详细记录见 [build-status.md](build-status.md)，硬件资料与确认过的引脚/器件见 [board-profile.md](board-profile.md)，终端操作见 [UI.md](UI.md)。

## 边界

本轮构建在 Windows 验证，跨平台 Python/Tcl 使用 pathlib、file join/normalize 等接口。Vivado/Vitis 的 Linux 主机构建待验证。后续的实体板验收见本页开头。

4条最终DRC提示来自AXI DMA内部FIFO的 `RAMB18E2/RAMB36E2_nochange_collision_advisory`；没有屏蔽DRC或降低严重级别。后续用实际DMA回环及压力测试验收数据通路。BD初始化还保留可选AXI USER位宽等厂商IP提示；Vitis厂商BSP编译存在宏/链接器提示，应用及最终链接成功。

PS_AVAILABLE_BYTES表示4GiB物理DDR扣除PL预留后的容量分工；固件和操作系统还会保留自身区域。低DDR尾部 `0x7ff00000..0x7fffffff` 的1MiB由PMU保留，诊断链接区和稀疏采样均避开它。高DDR实际范围是 `0x800000000..0x87fffffff`，更大的HP译码窗口不代表更多物理内存。

后续烧录/采集步骤见 `../../axu4ev_vitis/README.md`。程序区分PASS、FAIL、SKIP和MANUAL；自动测试fail为0仍需完成manual项验收。

## 最终产物

默认 bitstream、XSA、诊断 ELF 和 BOOT.BIN 的路径、大小和 SHA256 见 [build-manifest.json](build-manifest.json)。
