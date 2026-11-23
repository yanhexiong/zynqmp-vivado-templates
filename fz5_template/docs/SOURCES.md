# 板级参数依据（2026-11-18）

本次只读参考原始资料和现成工程，在当前工作区 `<repo-root>` 下建立新工程；没有修改 `<vendor-bundle>/FZ5` 或原 Vitis 工程。

## 资料优先级和采用方式

1. 用户提供的在线[硬件资料与实验勘误](https://fpga.yahenix.top/#errata)，内容实际由 `data.js` 的 `errata` 数组加载。快照保存在 `evidence/errata-2026-11-18.txt`，检索日期为 2026-11-18。
2. `<vendor-bundle>/FZ5/HardwareFiles/HardwareFiles/Schematic/MYS-ZU5EV-32E4D-EDGE_V13.pdf`。已提取全文并渲染检查第8页的 MIO/EEPROM/RUN 电路和第11页的 PL RS232 引脚。DDR 第9、17、18页显示 DDR 接到 PS 专用 DDR 引脚，无独立 PL DDR。
3. `<vendor-bundle>/FZ5/HardwareFiles/HardwareFiles/PIN_MAP_RouteLength/FZ5_BALL.csv`，用于交叉核对 MIO43/K19、MIO42/L18；不用可能误配的演示信号名称直接生成用户 LED XDC。
4. `<vendor-bundle>/FZ5/docs_md/EdgeBoard_AI_计算盒及计算卡硬件说明文档-V1.0.md`，板卡版本、接口、DDR/eMMC/EEPROM/PHY/USB。
5. `<vendor-bundle>/FZ5/docs_md/MYS-ZU5EV FPGA 指导手册.md` 第3章 PS 配置、第4章 AXI UART/IIC；4 GiB 与8 GiB 版本分别对应16/17位行地址。
6. `<vendor-bundle>/FZ5/SoftwareFiles/05-ProgrammableLogic_Source/hello_world.rar` 内 `hello_world.srcs/sources_1/bd/design_1/hw_handoff/design_1_bd.tcl`，原厂 2020.1 配置中的 MIO、USB/DP GTR/参考时钟路由。仅提取必要文本到临时目录，没有导入旧 IP 缓存或旧工程绝对路径。
7. `<reference-vitis-workspace>/hello_world_system` 及同工作区 `design_1_wrapper.xsa`、`hello_world/src/lscript.ld`。现有工程使用 Vivado/Vitis 2023.1、A53 standalone、8 GiB、-1 器件；XSA 的 `.hwh` 提供实际 PS DDR 参数，保存为 `board/reference_ddr_8g.json`。调试脚本用于参考 FSBL 初始化步骤，新脚本不沿用其固定电缆序列号或旧 bitstream。
8. 本地安装的 `<XILINX_VIVADO>` / `<XILINX_VITIS>`（验证基线为 2023.1）的 IP 元数据、驱动头文件/示例、XSCT `help`、启动环境脚本用于核对实际接口。其他版本可通过命令行或环境变量选择使用。

## 已落实的勘误与差异

- RUN/D46 是 **MIO43/K19**，经 Q2 驱动，高有效。**MIO42/L18 是风扇控制**；不得为了闪灯切换它。
- D46 是红绿双色封装，红色电源常亮，绿色受控；观察上可能显示红与黄绿/橙色交替。D3 是配置完成状态灯，不是软件 RUN 灯。
- **J1 是 JTAG，J13 是调试 UART Micro-USB**；快速指南把 JTAG 写成 J13 的地方不采用。
- 在线勘误确认教程 8 GiB 参数曾在实机通过 FSBL 训练。模板沿用参考 XSA 的几何和时序，本模板的实机结果见[验证记录](VALIDATION.md)。
- SD 镜像包含生成的 PMUFW。JTAG 脚本也在 FSBL 前加载并启动 PMUFW。[AMD JTAG 启动说明](https://docs.amd.com/r/2023.1-English/ug1137-zynq-ultrascale-mpsoc-swdev/Loading-PMU-Firmware-in-JTAG-Boot-Mode)
- 硬件手册写 -2，而 V13 图纸器件符号、BALL 文件和现成 XSA 使用 -1，因此默认 -1，同时保留速度等级菜单，最终以芯片丝印为准。
- 硬件手册把 AR8035 的 `0x4` 称为 “IIC 地址”，这里按原理图第20页 `PHY address:100` 解释为 **MDIO PHY 地址4**。实测的 FZ5D 在该地址返回 YT8511 的 `0000:010A`。I2C EEPROM 地址为 `0x51`。[Linux Motorcomm 驱动](https://github.com/torvalds/linux/blob/master/drivers/net/phy/motorcomm.c)
- 文档 SD1 示例曾打开 MIO44 写保护；原厂 BD 实际关闭 WP，V13 图纸 MIO44 为扩展脚。模板使用 MIO45 CD，不启用 WP。
- 原厂 `package.xdc` 的 G15 演示 `led` 不是 D46 的 PS MIO43。本模板不复用这个 LED 约束。
- DDR 的速度档 `DDR4_2400P` 与当前 PS DDR 控制器约600 MHz不是同一含义；不把档位值误报为实际运行时钟。

## 输入摘要

| 输入 | SHA256 |
|---|---|
| 参考 `design_1_wrapper.xsa` | `AE1A2B8FADBAF707610A46D229388819F5705E73F1F48CF1BA17E281CC7DD9BF` |
| 原厂 `hello_world.rar` | `A846258275980A6B8693CBD996B339B12FC7D7BC8A2E4B8DC9D01FD46D1D73BA` |
| V13 原理图 PDF | `80366A803D84CB28FBFB62645CE6E1786AC8BA29C2900D4A7352FA13961999D2` |
| `FZ5_BALL.csv` | `45AE363FF65D7EE6AB6752A2564FE956ACCA764AAAC26045F6996043DDE40880` |
