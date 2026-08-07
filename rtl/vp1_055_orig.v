//
// КР1801ВП1-055 -- the original, built from its own gate-array cells.
//
// This is a structural transcription of the die-level schematic published by
// the 1801BM1/k1801 project (055/sch/055.pdf), instantiating that project's
// own cell library from lib_1801.v.  It is the reference the substitute is
// checked against: not a description of what the chip is believed to do, but
// the cells it is actually built from, wired as the schematic wires them.
//
// Reading the schematic, per bit of the 16-bit port:
//
//   V0 --[tINPUT.y2]--> ~V0 --[t371]--> [t371] --> [t371] --> [tOUTPUT_OE] --> nA0
//   nA0 --[tINPUT.y2]--> ~nA0 --[t371]--> [t371] --> [t371] --> [tOUTPUT_OE] --> V0
//
// The W group (bits 8-15) is the same with ONE t371 instead of three.  The
// input pad's y2 output is the complement, so each direction carries
// 1 + 3 = 4 inversions in the V group and 1 + 1 = 2 in the W group -- both
// even, so the part is NON-INVERTING.  See docs/LOGIC.md; this matters,
// because an inverting substitute would invert the machine's whole bus.
//
// Delays come from the library and are in nanoseconds.
//
`timescale 1ns / 10ps

// One bit of the bidirectional port, parameterised by chain length.
module vp1_055_bit #(parameter STAGES = 3) (
   inout  wire v,          // V or W side pin
   inout  wire na,         // nA side pin
   input  wire oe_v_n,     // drive the V/W pin when low
   input  wire oe_na_n     // drive the nA pin when low
);
   wire v_in, na_in;                    // pad complement outputs
   wire [STAGES:0] fwd, rev;

   tINPUT pad_v  (.x1(v),  .y1(), .y2(v_in));
   tINPUT pad_na (.x1(na), .y1(), .y2(na_in));

   assign fwd[0] = v_in;                // V -> nA
   assign rev[0] = na_in;               // nA -> V

   genvar i;
   generate
      for (i = 0; i < STAGES; i = i + 1) begin : chain
         // t371 is a dual inverter: one section per direction, which is why
         // the schematic shows a single cell straddling both chains.
         t371 u (.x6(fwd[i]), .y4(fwd[i+1]),
                 .x1(rev[i]), .y3(rev[i+1]));
      end
   endgenerate

   tOUTPUT_OE drv_na (.x1(fwd[STAGES]), .x2(oe_na_n), .y1(na));
   tOUTPUT_OE drv_v  (.x1(rev[STAGES]), .x2(oe_v_n),  .y1(v));
endmodule


module vp1_055_orig (
   inout  wire [7:0]  v,      // pins 1-8
   inout  wire [7:0]  w,      // pins 9-16
   inout  wire [15:0] na,     // pins 22-37
   output wire [2:0]  a,      // pins 17-19
   input  wire [2:0]  c,      // pins 38-40
   input  wire        dir,    // pin 20, nA/VW
   input  wire        oe_n    // pin 41, nOE
);
   // ---- the control block -------------------------------------------------
   //
   //   A21 = t370 inverter on DIR
   //   J21 = t373 NOR(oe_n, dir)        -> K21 = t429 inverter -> four t428
   //   B21 = t373 NOR(oe_n, ~dir)       -> E17 = t429 inverter -> four t428
   //
   // The t428s are non-inverting fanout buffers, so each chain's enable is
   // simply the NOR re-inverted:  oe_n | dir  and  oe_n | ~dir.  tOUTPUT_OE
   // disables on a HIGH, so a driver is on when its term is 0 -- that is,
   // when oe_n = 0 and dir picks that side.
   wire dir_n, j21, b21, k21, e17;
   wire en_na_n, en_v_n;

   t370 a21 (.x5(dir),   .y2(dir_n));
   t373 j21c(.x1(oe_n),  .x3(dir),   .y4(j21));
   t373 b21c(.x1(oe_n),  .x3(dir_n), .y4(b21));
   t429 k21c(.x5(j21),   .y3(k21));
   t429 e17c(.x5(b21),   .y3(e17));
   // One representative t428 per chain.  The die has four each, purely for
   // fanout across the sixteen bit slices; they are logically identical and
   // collapsing them costs the model nothing but 3 ns of fanout delay.
   t428 e23c(.x2(k21),   .y3(en_na_n));
   t428 k15c(.x2(e17),   .y3(en_v_n));

   // ---- the sixteen bidirectional bits ------------------------------------
   genvar i;
   generate
      for (i = 0; i < 8; i = i + 1) begin : vbits      // three-stage group
         vp1_055_bit #(.STAGES(3)) b (
            .v(v[i]), .na(na[i]), .oe_v_n(en_v_n), .oe_na_n(en_na_n));
      end
      for (i = 0; i < 8; i = i + 1) begin : wbits      // one-stage group
         vp1_055_bit #(.STAGES(1)) b (
            .v(w[i]), .na(na[i+8]), .oe_v_n(en_v_n), .oe_na_n(en_na_n));
      end
   endgenerate

   // ---- the three unidirectional buffers ----------------------------------
   //
   // C0-C2 -> A0-A2, taken off the pad's TRUE output (y1) with no inverter in
   // the path, and with the output driver's OE tied to ground on the die --
   // so these are non-inverting and permanently enabled.  pin 41 does not
   // reach them, which the datasheet text agrees with: it lists only nA, V
   // and W as disabled.
   generate
      for (i = 0; i < 3; i = i + 1) begin : cbits
         wire t;
         tINPUT     pad (.x1(c[i]), .y1(t), .y2());
         tOUTPUT_OE drv (.x1(t), .x2(1'b0), .y1(a[i]));
      end
   endgenerate
endmodule
