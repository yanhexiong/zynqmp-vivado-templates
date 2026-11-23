/* FZ5 standalone A53 bring-up. Storage tests never erase or program media. */
#include "fz5_config.h"
#include "test_options.h"
#include "xparameters.h"
#include "xil_printf.h"
#include "xil_cache.h"
#include "xil_io.h"
#include "xil_mmu.h"
#include "xgpiops.h"
#include "xtime_l.h"
#include "sleep.h"
#include "xstatus.h"
#include <string.h>
#if FZ5_PS_UART1
#include "xuartps.h"
#endif
#if FZ5_PS_I2C1
#include "xiicps.h"
#endif
#if FZ5_PS_GEM3
#include "xemacps.h"
#endif
#if FZ5_PS_CAN1
#include "xcanps.h"
#endif
#if DIAG_TEST_STORAGE && (FZ5_PS_EMMC || FZ5_PS_SD)
#include "xsdps.h"
#include "xsdps_core.h"
#endif
#if FZ5_PS_QSPI
#include "xqspipsu.h"
#endif
#if FZ5_PL_DMA
#include "xaxidma.h"
#endif

enum verdict { PASS, FAIL, SKIP, MANUAL };
static unsigned counts[4];
static XGpioPs gpio;

static void result(const char *test, enum verdict v, const char *detail)
{
    const char *names[] = {"PASS", "FAIL", "SKIP", "MANUAL"};
    ++counts[v];
    xil_printf("[%s] %s: %s\r\n", names[v], test, detail);
}

static u64 milliseconds(void)
{
    XTime t;
    XTime_GetTime(&t);
    return (u64)t / (COUNTS_PER_SECOND / 1000U);
}

static int timed_out(u64 start)
{
    return milliseconds() - start > DIAG_TIMEOUT_MS;
}

static void gpio_out(unsigned pin, unsigned value)
{
    /* Set output latch before enabling output: avoid reset/power glitches. */
    XGpioPs_WritePin(&gpio, pin, value);
    XGpioPs_SetDirectionPin(&gpio, pin, 1);
    XGpioPs_SetOutputEnablePin(&gpio, pin, 1);
}

static int board_init(void)
{
    XGpioPs_Config *c = XGpioPs_LookupConfig(XPAR_PSU_GPIO_0_DEVICE_ID);
    if (!c || XGpioPs_CfgInitialize(&gpio, c, c->BaseAddr) != XST_SUCCESS)
        return XST_FAILURE;
    gpio_out(33, 0); /* external WDT remains disabled; no watchdog service loop */
#if FZ5_PS_UART1
    gpio_out(11, 0); /* RS485 receive mode */
#endif
#if FZ5_PS_GEM3
    gpio_out(30, 0);
    usleep(20000);
    gpio_out(30, 1);
    usleep(100000);
#endif
#if FZ5_PS_USB0
    gpio_out(39, 0); /* USB3320 reset */
    gpio_out(40, 0); /* USB5744 reset */
    usleep(20000);
    gpio_out(39, 1);
    usleep(20000);
    gpio_out(40, 1);
#endif
    /* MIO31/32 are board power enables; never toggle. MIO42 is FAN_CTRL. */
    return XST_SUCCESS;
}

static void test_led(void)
{
#if DIAG_TEST_LED
    unsigned old = XGpioPs_ReadPin(&gpio, FZ5_RUN_LED_MIO);
    for (unsigned i = 0; i < 6; ++i) {
        gpio_out(FZ5_RUN_LED_MIO, i & 1U);
        usleep(200000);
    }
    gpio_out(FZ5_RUN_LED_MIO, old);
    result("RUN LED MIO43", MANUAL, "confirm D46 red/yellow-green alternation; D3 stays on");
#else
    result("RUN LED", SKIP, "disabled in test_options.h");
#endif
}

static void test_memory(void)
{
#if DIAG_TEST_MEMORY
    static volatile u32 buffer[4096] __attribute__((aligned(64)));
    int ok = 1;
    for (unsigned i = 0; i < 4096; ++i) buffer[i] = 0xA55A0000U ^ i;
    Xil_DCacheFlushRange((UINTPTR)buffer, sizeof buffer);
    Xil_DCacheInvalidateRange((UINTPTR)buffer, sizeof buffer);
    for (unsigned i = 0; i < 4096; ++i) if (buffer[i] != (0xA55A0000U ^ i)) ok = 0;
    result("PS low DDR", ok ? PASS : FAIL, "16 KiB write/read with cache maintenance");

    /* Distinct simultaneous values detect aliased 4-GiB/8-GiB geometry.
     * Samples are in otherwise unused high DDR, and original words are restored. */
    UINTPTR addr[8];
    u64 saved[8];
    unsigned n = (unsigned)(FZ5_DDR_HIGH_SIZE >> 30);
    for (unsigned i = 0; i < n; ++i) {
        addr[i] = (UINTPTR)(FZ5_DDR_HIGH_BASE + ((u64)i << 30) + 0x100000U);
        Xil_SetTlbAttributes(addr[i], NORM_NONCACHE);
        saved[i] = Xil_In64(addr[i]);
    }
    for (unsigned i = 0; i < n; ++i) Xil_Out64(addr[i], 0xF25D000000000000ULL | (u64)addr[i]);
    ok = 1;
    for (unsigned i = 0; i < n; ++i)
        if (Xil_In64(addr[i]) != (0xF25D000000000000ULL | (u64)addr[i])) ok = 0;
    for (unsigned i = 0; i < n; ++i) Xil_Out64(addr[i], saved[i]);
    result("PS high DDR geometry", ok ? PASS : FAIL, "one saved/restored sample per GiB; sparse test only");
#else
    result("DDR", SKIP, "disabled in test_options.h");
#endif
}

static void test_i2c(void)
{
#if FZ5_PS_I2C1
    XIicPs iic;
    XIicPs_Config *c = XIicPs_LookupConfig(XPAR_PSU_I2C_1_DEVICE_ID);
    u8 offset[2] = {0, 0}, data[16];
    int rc = c ? XIicPs_CfgInitialize(&iic, c, c->BaseAddress) : XST_FAILURE;
    if (rc == XST_SUCCESS) rc = XIicPs_SetSClk(&iic, 100000);
    if (rc == XST_SUCCESS) rc = XIicPs_MasterSendPolled(&iic, offset, 2, 0x51);
    if (rc == XST_SUCCESS) {
        u64 start = milliseconds();
        while (XIicPs_BusIsBusy(&iic) && !timed_out(start)) { }
        rc = XIicPs_BusIsBusy(&iic) ? XST_FAILURE : XIicPs_MasterRecvPolled(&iic, data, sizeof data, 0x51);
    }
    if (rc == XST_SUCCESS) {
        xil_printf("EEPROM[0:15] =");
        for (unsigned i = 0; i < sizeof data; ++i) xil_printf(" %02x", data[i]);
        xil_printf("\r\n");
    }
    result("I2C1 EEPROM 0x51", rc == XST_SUCCESS ? PASS : FAIL, "read only; no data programming");
    result("I2C1 clock/PMIC/security", MANUAL, "not modified or qualified by EEPROM test");
#else
    result("I2C1", SKIP, "controller disconnected");
#endif
}

static void test_ethernet(void)
{
#if FZ5_PS_GEM3
    XEmacPs mac = {0};
    XEmacPs_Config *c = XEmacPs_LookupConfig(XPAR_PSU_ETHERNET_3_DEVICE_ID);
    u16 id1 = 0, id2 = 0, status = 0;
    int rc = c ? XEmacPs_CfgInitialize(&mac, c, c->BaseAddress) : XST_FAILURE;
    if (rc == XST_SUCCESS) {
        XEmacPs_SetMdioDivisor(&mac, MDC_DIV_224);
        rc = XEmacPs_PhyRead(&mac, 4, 2, &id1);
        if (rc == XST_SUCCESS) rc = XEmacPs_PhyRead(&mac, 4, 3, &id2);
        if (rc == XST_SUCCESS) rc = XEmacPs_PhyRead(&mac, 4, 1, &status);
        if (rc == XST_SUCCESS) rc = XEmacPs_PhyRead(&mac, 4, 1, &status);
    }
    const u32 phy_id = ((u32)id1 << 16) | id2;
    const char *model = phy_id == 0x0000010aU ? "YT8511" :
                        phy_id == 0x004dd072U ? "AR8035" : "unknown";
    const int ok = rc == XST_SUCCESS && (phy_id == 0x0000010aU || phy_id == 0x004dd072U)
                   && status != 0 && status != 0xffffU;
    xil_printf("PHY@4 ID=%04x:%04x model=%s BMSR=%04x link=%s rc=%d\r\n",
               id1, id2, model, status, ok ? ((status & 0x0004U) ? "up" : "down") : "unknown", rc);
    result("GEM3 MDIO", ok ? PASS : FAIL, "reads PHY identity and link status");
    result("Ethernet packets/RGMII", MANUAL, "run Linux peer iperf/ping before qualification");
#else
    result("GEM3", SKIP, "controller disconnected");
#endif
}

static void test_can(void)
{
#if FZ5_PS_CAN1
    XCanPs can;
    XCanPs_Config *c = XCanPs_LookupConfig(XPAR_PSU_CAN_1_DEVICE_ID);
    int rc = c ? XCanPs_CfgInitialize(&can, c, c->BaseAddr) : XST_FAILURE;
    if (rc == XST_SUCCESS) rc = XCanPs_SelfTest(&can);
    result("CAN1 controller", rc == XST_SUCCESS ? PASS : FAIL, "register self-test only");
    result("CAN1 physical bus", MANUAL, "requires terminated CAN peer; controller self-test cannot qualify it");
#else
    result("CAN1", SKIP, "controller disconnected");
#endif
}

#if DIAG_TEST_STORAGE && (FZ5_PS_EMMC || FZ5_PS_SD)
static void sd_status(const char *name, const char *stage, int rc, UINTPTR base)
{
    const u32 state = XSdPs_ReadReg(base, XSDPS_PRES_STATE_OFFSET);
    const u16 cmd = XSdPs_ReadReg16(base, XSDPS_CMD_OFFSET);
    xil_printf("%s %s rc=%d present=%08x clock=%04x cmd=%u intr=%04x err=%04x adma=%02x\r\n",
               name, stage, rc, state, XSdPs_ReadReg16(base, XSDPS_CLK_CTRL_OFFSET),
               (cmd & XSDPS_CMD_MASK) >> 8, XSdPs_ReadReg16(base, XSDPS_NORM_INTR_STS_OFFSET),
               XSdPs_ReadReg16(base, XSDPS_ERR_INTR_STS_OFFSET), XSdPs_ReadReg8(base, XSDPS_ADMA_ERR_STS_OFFSET));
}

static void test_sd_device(u16 device_id, const char *name, int embedded)
{
    static XSdPs sd;
    static u8 sector[512] __attribute__((aligned(64)));
    XSdPs_Config *cfg = XSdPs_LookupConfig(device_id);
    if (!cfg) {
        result(name, FAIL, "controller missing from the Vitis BSP");
        return;
    }

    /* CfgInitialize checks IsReady before clearing anything. Reset it for each host. */
    memset(&sd, 0, sizeof sd);
    const char *stage = "CfgInitialize";
    int rc = XSdPs_CfgInitialize(&sd, cfg, cfg->BaseAddress);
    if (rc != XST_SUCCESS) goto failed;

    if (!embedded && cfg->CardDetect) {
        u32 state;
        const u64 start = milliseconds();
        do {
            state = XSdPs_ReadReg(cfg->BaseAddress, XSDPS_PRES_STATE_OFFSET);
            if (state & XSDPS_PSR_CARD_STABLE_MASK) break;
            usleep(1000);
        } while (!timed_out(start));
        if (!(state & XSDPS_PSR_CARD_STABLE_MASK)) {
            result(name, FAIL, "card detect did not stabilize");
            sd_status(name, "card detect", XST_FAILURE, cfg->BaseAddress);
            return;
        }
        if (!(state & XSDPS_PSR_CARD_INSRT_MASK)) {
            result(name, SKIP, "no card detected at J4");
            return;
        }
    }

    sd.BusWidth = XSDPS_1_BIT_WIDTH;
    sd.BusSpeed = XSDPS_CLK_400_KHZ;
    sd.CardType = embedded ? XSDPS_CHIP_EMMC : XSDPS_CARD_SD;
    stage = "Change_ClkFreq (400 kHz)";
    rc = XSdPs_Change_ClkFreq(&sd, sd.BusSpeed);
    if (rc != XST_SUCCESS) goto failed;

    if (embedded) {
        /* Keep legacy timing. The full BSP mode init may permanently program RST_N_FUNCTION. */
        stage = "MmcCardEnum";
        rc = XSdPs_MmcCardEnum(&sd);
        if (rc != XST_SUCCESS) goto failed;
        sd.BusWidth = XSDPS_8_BIT_WIDTH;
        stage = "Change_BusWidth (eMMC 8-bit)";
        rc = XSdPs_Change_BusWidth(&sd);
        if (rc != XST_SUCCESS) goto failed;
        stage = "SetBlkSize";
        rc = XSdPs_SetBlkSize(&sd, sizeof sector);
        if (rc != XST_SUCCESS) goto failed;
    } else {
        stage = "SdCardInitialize";
        rc = XSdPs_SdCardInitialize(&sd);
        if (rc != XST_SUCCESS) goto failed;
    }
    stage = "ReadPolled (LBA 0)";
    rc = XSdPs_ReadPolled(&sd, 0, 1, sector);
    if (rc != XST_SUCCESS) goto failed;

    result(name, PASS, embedded ? "8-bit legacy mode, read sector 0" : "initialized and read sector 0");
    return;

failed:
    result(name, FAIL, stage);
    sd_status(name, stage, rc, cfg->BaseAddress);
}
#endif

static void test_storage(void)
{
#if DIAG_TEST_STORAGE && FZ5_PS_QSPI
    XQspiPsu q;
    XQspiPsu_Config *c = XQspiPsu_LookupConfig(XPAR_PSU_QSPI_0_DEVICE_ID);
    XQspiPsu_Msg msg[2];
    u8 cmd = 0x9f, id[3] = {0};
    memset(msg, 0, sizeof msg);
    int rc = c ? XQspiPsu_CfgInitialize(&q, c, c->BaseAddress) : XST_FAILURE;
    if (rc == XST_SUCCESS) {
        XQspiPsu_SelectFlash(&q, XQSPIPSU_SELECT_FLASH_CS_LOWER, XQSPIPSU_SELECT_FLASH_BUS_LOWER);
        rc = XQspiPsu_SetClkPrescaler(&q, XQSPIPSU_CLK_PRESCALE_32);
        msg[0].TxBfrPtr = &cmd; msg[0].ByteCount = 1;
        msg[0].BusWidth = XQSPIPSU_SELECT_MODE_SPI; msg[0].Flags = XQSPIPSU_MSG_FLAG_TX;
        msg[1].RxBfrPtr = id; msg[1].ByteCount = 3;
        msg[1].BusWidth = XQSPIPSU_SELECT_MODE_SPI; msg[1].Flags = XQSPIPSU_MSG_FLAG_RX;
        if (rc == XST_SUCCESS) rc = XQspiPsu_PolledTransfer(&q, msg, 2);
    }
    xil_printf("QSPI JEDEC=%02x:%02x:%02x\r\n", id[0], id[1], id[2]);
    result("QSPI JEDEC", rc == XST_SUCCESS && id[0] == 0x20 && id[2] == 0x20 ? PASS : FAIL, "Micron 512Mbit ID; no erase/write");
#else
    result("QSPI ID", SKIP, "controller or storage test disabled");
#endif
#if DIAG_TEST_STORAGE && FZ5_PS_EMMC
    test_sd_device(XPAR_PSU_SD_0_DEVICE_ID, "SD0 eMMC", 1);
#endif
#if DIAG_TEST_STORAGE && FZ5_PS_SD
    test_sd_device(XPAR_PSU_SD_1_DEVICE_ID, "SD1 TF card", 0);
#endif
#if !DIAG_TEST_STORAGE || !(FZ5_PS_EMMC || FZ5_PS_SD)
    result("SD/eMMC", SKIP, "controllers or storage test disabled");
#endif
}

static void test_pl(void)
{
#if FZ5_PL_GPIO
    xil_printf("[RUN] PL AXI GPIO\r\n");
    int ok = 1;
    Xil_Out32(FZ5_GPIO_BASE + 4, 0); /* channel 1 all outputs */
    Xil_Out32(FZ5_GPIO_BASE + 12, 0xffffffffU); /* channel 2 inputs */
    for (unsigned i = 0; i < 32; ++i) {
        u32 pattern = 1U << i;
        Xil_Out32(FZ5_GPIO_BASE, pattern);
        if (Xil_In32(FZ5_GPIO_BASE + 8) != pattern) ok = 0;
    }
    result("PL AXI GPIO", ok ? PASS : FAIL, "32 walking-one output/input loopback");
#else
    result("PL AXI GPIO", SKIP, "IP not instantiated");
#endif
#if FZ5_PL_BRAM
    xil_printf("[RUN] PL AXI BRAM\r\n");
    int bram_ok = 1;
    for (unsigned i = 0; i < FZ5_BRAM_SIZE; i += 4) Xil_Out32(FZ5_BRAM_BASE + i, 0xb4a00000U ^ i);
    for (unsigned i = 0; i < FZ5_BRAM_SIZE; i += 4)
        if (Xil_In32(FZ5_BRAM_BASE + i) != (0xb4a00000U ^ i)) bram_ok = 0;
    result("PL AXI BRAM", bram_ok ? PASS : FAIL, "full 64 KiB address-pattern write/read");
#else
    result("PL AXI BRAM", SKIP, "IP not instantiated");
#endif
#if FZ5_PL_DMA
    xil_printf("[RUN] PL DMA high-DDR loopback\r\n");
    XAxiDma dma;
    XAxiDma_Config *c = XAxiDma_LookupConfig(XPAR_AXIDMA_0_DEVICE_ID);
    int rc = c ? XAxiDma_CfgInitialize(&dma, c) : XST_FAILURE;
    const unsigned len = 4096;
    UINTPTR tx = (UINTPTR)(FZ5_PL_POOL_BASE + 0x200000U);
    UINTPTR rx = tx + 0x10000U;
    Xil_SetTlbAttributes(tx, NORM_NONCACHE);
    u8 *src = (u8 *)tx, *dst = (u8 *)rx;
    for (unsigned i = 0; i < len; ++i) { src[i] = (u8)(i ^ (i >> 8) ^ 0xa5); dst[i] = 0; }
    Xil_DCacheFlushRange(tx, len);
    Xil_DCacheFlushRange(rx, len);
    if (rc == XST_SUCCESS) {
        XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DMA_TO_DEVICE);
        XAxiDma_IntrDisable(&dma, XAXIDMA_IRQ_ALL_MASK, XAXIDMA_DEVICE_TO_DMA);
        rc = XAxiDma_SimpleTransfer(&dma, rx, len, XAXIDMA_DEVICE_TO_DMA);
        if (rc == XST_SUCCESS) rc = XAxiDma_SimpleTransfer(&dma, tx, len, XAXIDMA_DMA_TO_DEVICE);
        u64 start = milliseconds();
        while (rc == XST_SUCCESS && (XAxiDma_Busy(&dma, XAXIDMA_DMA_TO_DEVICE) || XAxiDma_Busy(&dma, XAXIDMA_DEVICE_TO_DMA))) {
            if (timed_out(start)) { rc = XST_FAILURE; break; }
        }
        u32 txs = Xil_In32(FZ5_DMA_BASE + 0x04U), rxs = Xil_In32(FZ5_DMA_BASE + 0x34U);
        xil_printf("DMA status TX=%08x RX=%08x @%08x%08x\r\n", txs, rxs, (u32)(tx >> 32), (u32)tx);
        if ((txs | rxs) & XAXIDMA_ERR_ALL_MASK) rc = XST_FAILURE;
    }
    Xil_DCacheInvalidateRange(rx, len);
    if (rc == XST_SUCCESS && memcmp(src, dst, len)) rc = XST_FAILURE;
    result("PL DMA high-DDR loopback", rc == XST_SUCCESS ? PASS : FAIL, "4 KiB MM2S -> AXIS FIFO -> S2MM, above 4 GiB");
    if (c) XAxiDma_Reset(&dma);
#else
    result("PL DMA", SKIP, "IP not instantiated / no reserved DDR");
#endif
}

static void test_serial(void)
{
#if DIAG_EXTERNAL_LOOPBACK && FZ5_PS_UART1
    XUartPs uart;
    XUartPs_Config *c = XUartPs_LookupConfig(XPAR_PSU_UART_1_DEVICE_ID);
    int rc = c ? XUartPs_CfgInitialize(&uart, c, c->BaseAddress) : XST_FAILURE;
    const u8 tx[] = {0x55, 0xaa, 0x12, 0x34};
    u8 rx[sizeof tx] = {0};
    if (rc == XST_SUCCESS) {
        XUartPs_SetBaudRate(&uart, 115200);
        gpio_out(11, 1);
        XUartPs_Send(&uart, (u8 *)tx, sizeof tx);
        u64 start = milliseconds();
        while (XUartPs_IsSending(&uart) && !timed_out(start)) { }
        if (timed_out(start)) rc = XST_FAILURE;
        usleep(1000);
        gpio_out(11, 0); /* peer must echo after this receive turnaround */
        unsigned received = 0;
        start = milliseconds();
        while (received < sizeof rx && !timed_out(start)) received += XUartPs_Recv(&uart, rx + received, sizeof rx - received);
        if (received != sizeof rx || memcmp(tx, rx, sizeof tx)) rc = XST_FAILURE;
    }
    result("UART1 RS485 echo", rc == XST_SUCCESS ? PASS : FAIL, "requires delayed echo from external peer");
#elif FZ5_PS_UART1
    result("UART1 RS485", MANUAL, "enable external loop test and connect delayed-echo peer");
#else
    result("UART1 RS485", SKIP, "controller disconnected");
#endif
#if FZ5_PL_RS232 && DIAG_EXTERNAL_LOOPBACK
    const u8 ch = 0x5a;
    Xil_Out32(FZ5_RS232_BASE + 12, 3); /* reset TX/RX FIFO */
    Xil_Out32(FZ5_RS232_BASE + 4, ch);
    u64 start232 = milliseconds();
    while (!(Xil_In32(FZ5_RS232_BASE + 8) & 1U) && !timed_out(start232)) { }
    int ok232 = !timed_out(start232) && (u8)Xil_In32(FZ5_RS232_BASE) == ch;
    result("PL RS232 J12 loopback", ok232 ? PASS : FAIL, "requires J12 TX/RX loopback fixture");
#elif FZ5_PL_RS232
    result("PL RS232 J12", MANUAL, "enable external loop test with connector fixture");
#else
    result("PL RS232 J12", SKIP, "IP not instantiated");
#endif
}

int main(void)
{
    xil_printf("\r\nFZ5_DIAG_BEGIN config=%s board=%s\r\n", FZ5_CONFIG_ID, FZ5_BOARD_NAME);
    xil_printf("DDR PS=%u MiB PL=%u MiB PL-pool=%08x%08x\r\n", (unsigned)(FZ5_PS_AVAILABLE_BYTES >> 20), FZ5_PL_RESERVED_MB, (u32)((u64)FZ5_PL_POOL_BASE >> 32), (u32)FZ5_PL_POOL_BASE);
    result("UART0 J13 console", PASS, "115200 8N1; capture of this text verifies TX path");
    if (board_init() != XST_SUCCESS) {
        result("PS GPIO initialization", FAIL, "cannot configure board reset controls");
    } else {
        test_led();
        test_memory();
        test_i2c();
        test_ethernet();
        test_can();
        test_storage();
        test_pl();
        test_serial();
    }
    result("USB0 host/hub", FZ5_PS_USB0 ? MANUAL : SKIP, "enabled: validate enumeration in Linux; no bare-metal host stack here");
    result("DisplayPort", FZ5_PS_DP ? MANUAL : SKIP, "enabled: validate link/video with monitor in Linux");
    result("RTC retention", FZ5_PS_RTC ? MANUAL : SKIP, "battery and power-cycle measurement required");
    xil_printf("FZ5_DIAG_END config=%s pass=%u fail=%u skip=%u manual=%u\r\n", FZ5_CONFIG_ID, counts[PASS], counts[FAIL], counts[SKIP], counts[MANUAL]);
    for (;;) { usleep(100000); }
    return 0;
}
