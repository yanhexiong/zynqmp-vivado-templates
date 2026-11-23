//Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
//Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
//--------------------------------------------------------------------------------
//Tool Version: Vivado v.2023.1 (win64) Build 3865809 Sun May  7 15:05:29 MDT 2023
//Date        : Fri Nov 20 16:30:30 2026
//Host        : build-host (sanitized)
//Command     : generate_target axu4ev_system_wrapper.bd
//Design      : axu4ev_system_wrapper
//Purpose     : IP block netlist
//--------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

module axu4ev_system_wrapper
   (pl_uart_rx,
    pl_uart_tx);
  input pl_uart_rx;
  output pl_uart_tx;

  wire pl_uart_rx;
  wire pl_uart_tx;

  axu4ev_system axu4ev_system_i
       (.pl_uart_rx(pl_uart_rx),
        .pl_uart_tx(pl_uart_tx));
endmodule
