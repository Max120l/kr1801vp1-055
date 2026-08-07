//
// The substitute: two 74x245 octal transceivers and three buffer sections.
//
// Modelled as the catalogue parts actually are, wired the way the board wires
// them, so the equivalence test is a statement about the board and not about a
// convenient abstraction of it.
//
// 74x245: DIR high  -> A drives B
//         DIR low   -> B drives A
//         /OE high  -> both sides high-Z
//
// The mapping that makes it a drop-in with no glue at all:
//
//         nA bus  -> the '245 A side
//         V / W   -> the '245 B side
//         pin 20  -> DIR, directly
//         pin 41  -> /OE, directly
//
// Check it against the original's control block:
//   dir = 1 -> original enables the V/W drivers (oe_n | ~dir = 0)
//           -> '245 with A=nA, DIR=1 drives B = V/W.            agrees
//   dir = 0 -> original enables the nA drivers  (oe_n | dir = 0)
//           -> '245 with DIR=0 drives A = nA.                    agrees
//
// The three-bit buffer is any always-on non-inverting section: three gates of
// a 74x244/'541 with /OE grounded, or a 74x125.  NOT a '240/'244-inverting
// variant -- these three are non-inverting on the die.
//
// Timing: the delays here are 74AHC-class typicals at 5 V, chosen because they
// sit closest to the original.  See docs/DESIGN.md for the comparison and for
// what is lost by giving both bytes the same delay.
//
`timescale 1ns / 10ps

`ifndef T245
`define T245 5.5        // 74AHC245 typical propagation, 5 V
`endif
`ifndef T245_EN
`define T245_EN 7.0     // /OE to output active/inactive
`endif
`ifndef T244
`define T244 5.0
`endif

module x245 (
   inout wire [7:0] a,
   inout wire [7:0] b,
   input wire       dir,
   input wire       oe_n
);
   wire drive_b = ~oe_n &  dir;
   wire drive_a = ~oe_n & ~dir;

   // Gate primitives rather than a conditional assign, so an undriven input
   // produces x on the output the way a real buffer does.  A `? :` would pass
   // z straight through and quietly claim the substitute floats its outputs
   // when its inputs float -- which no CMOS part does, and which would hide
   // exactly the contention a bench test is looking for.
   genvar i;
   generate
      for (i = 0; i < 8; i = i + 1) begin : slice
`ifdef MUTANT_INVERTING
         // A 74x640 in place of the '245.  This is the mistake the earlier
         // notes in the sibling repo would have led to, and it is invisible
         // on a schematic: same package, same pinout, one letter different.
         notif1 #(`T245) to_b (b[i], a[i], drive_b);
         notif1 #(`T245) to_a (a[i], b[i], drive_a);
`elsif MUTANT_DIR
         // DIR wired backwards.
         bufif1 #(`T245) to_b (b[i], a[i], drive_a);
         bufif1 #(`T245) to_a (a[i], b[i], drive_b);
`else
         bufif1 #(`T245) to_b (b[i], a[i], drive_b);
         bufif1 #(`T245) to_a (a[i], b[i], drive_a);
`endif
      end
   endgenerate
endmodule

module vp1_055_repl (
   inout  wire [7:0]  v,
   inout  wire [7:0]  w,
   inout  wire [15:0] na,
   output wire [2:0]  a,
   input  wire [2:0]  c,
   input  wire        dir,
   input  wire        oe_n
);
   // U1 carries the low byte (V group), U2 the high byte (W group).
   x245 u1 (.a(na[7:0]),  .b(v), .dir(dir), .oe_n(oe_n));
   x245 u2 (.a(na[15:8]), .b(w), .dir(dir), .oe_n(oe_n));

   // U3: three sections, permanently enabled, non-inverting.
`ifdef MUTANT_C_GATED
   // The plausible-looking error: tie this buffer's enable to pin 41 along
   // with everything else.  On the die its enable is grounded.
   bufif0 #(`T244) b0 (a[0], c[0], oe_n);
   bufif0 #(`T244) b1 (a[1], c[1], oe_n);
   bufif0 #(`T244) b2 (a[2], c[2], oe_n);
`else
   buf #(`T244) b0 (a[0], c[0]);
   buf #(`T244) b1 (a[1], c[1]);
   buf #(`T244) b2 (a[2], c[2]);
`endif
endmodule
