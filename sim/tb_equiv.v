//
// Does the substitute behave like the chip it replaces?
//
// Drives both models from one set of stimulus and compares every pin after
// each settles.  The point is to catch the two mistakes that would be
// expensive to find on a bench:
//
//   * a polarity error -- an inverting transceiver where the die is
//     non-inverting, which would invert the machine's entire address/data bus
//   * a direction-sense error -- DIR wired backwards, which turns every read
//     into a bus fight with the processor
//
// Both are single wires on a schematic and neither announces itself; the
// machine simply does not run.
//
`timescale 1ns / 10ps

module tb_equiv;

   // Stimulus.  Each side is driven through a per-bit enable so a pin can be
   // released and the model left to drive it, which is the whole point of a
   // transceiver and the only way a direction error becomes visible.
   reg [15:0] na_drv, vw_drv;
   reg        na_en,  vw_en;
   reg [2:0]  c;
   reg        dir, oe_n;

   wire [15:0] na_o, na_r;
   wire [7:0]  v_o,  w_o,  v_r,  w_r;
   wire [2:0]  a_o,  a_r;

   assign na_o = na_en ? na_drv : 16'bz;
   assign na_r = na_en ? na_drv : 16'bz;
   assign {w_o, v_o} = vw_en ? vw_drv : 16'bz;
   assign {w_r, v_r} = vw_en ? vw_drv : 16'bz;

   vp1_055_orig dut_o (.v(v_o), .w(w_o), .na(na_o), .a(a_o),
                       .c(c), .dir(dir), .oe_n(oe_n));
   vp1_055_repl dut_r (.v(v_r), .w(w_r), .na(na_r), .a(a_r),
                       .c(c), .dir(dir), .oe_n(oe_n));

   integer errors = 0;
   integer checks = 0;

   task check(input [255:0] what);
      begin
         checks = checks + 1;
         if (na_o !== na_r || v_o !== v_r || w_o !== w_r || a_o !== a_r) begin
            errors = errors + 1;
            $display("  MISMATCH  %0s", what);
            $display("      orig  nA=%b w=%b v=%b a=%b", na_o, w_o, v_o, a_o);
            $display("      repl  nA=%b w=%b v=%b a=%b", na_r, w_r, v_r, a_r);
         end
      end
   endtask

   // Present a pattern on the driven side and let both models settle.
   // 200 ns is comfortably past the original's slowest path (a V-group bit is
   // ~34 ns of cells plus a 16.5 ns output pad).
   task drive_na(input [15:0] d);
      begin na_en = 1; vw_en = 0; na_drv = d; #200; end
   endtask
   task drive_vw(input [15:0] d);
      begin vw_en = 1; na_en = 0; vw_drv = d; #200; end
   endtask

   integer i;
   reg [15:0] pat;

   initial begin
      $display("KR1801VP1-055: original (die cells) vs substitute (74x245)");
      $display("");

      // ---- 1. direction high: nA is the source, V/W are driven -----------
      $display("dir=1  nA -> V/W");
      oe_n = 0; dir = 1; c = 3'b000;
      drive_na(16'h0000); check("dir=1 all zero");
      drive_na(16'hFFFF); check("dir=1 all one");
      drive_na(16'hAAAA); check("dir=1 alternating");
      drive_na(16'h5555); check("dir=1 alternating, inverse");
      // walking one: catches a swapped or stuck bit, and catches the low/high
      // byte being wired to the wrong transceiver.
      for (i = 0; i < 16; i = i + 1) begin
         pat = 16'h0001 << i;
         drive_na(pat); check("dir=1 walking one");
      end

      // ---- 2. direction low: V/W are the source, nA is driven ------------
      $display("dir=0  V/W -> nA");
      dir = 0;
      drive_vw(16'h0000); check("dir=0 all zero");
      drive_vw(16'hFFFF); check("dir=0 all one");
      drive_vw(16'hAAAA); check("dir=0 alternating");
      drive_vw(16'h5555); check("dir=0 alternating, inverse");
      for (i = 0; i < 16; i = i + 1) begin
         pat = 16'h0001 << i;
         drive_vw(pat); check("dir=0 walking one");
      end

      // ---- 3. /OE high: everything off, both directions ------------------
      //
      // A substitute that stays enabled here would contend with the processor
      // every time the machine deselects the buffer.
      $display("oe_n=1  both sides high-Z");
      oe_n = 1;
      drive_na(16'hAAAA); check("oe_n=1, dir=0, nA driven");
      dir = 1;
      drive_na(16'h5555); check("oe_n=1, dir=1, nA driven");
      drive_vw(16'hAAAA); check("oe_n=1, dir=1, V/W driven");
      na_en = 0; vw_en = 0; #200;
      check("oe_n=1, nothing driven");

      // ---- 4. the three-bit buffer ---------------------------------------
      //
      // Checked with /OE HIGH as well as low, because on the die its enable is
      // grounded: pin 41 must NOT switch it off.  A substitute that ties this
      // buffer's enable to pin 41 passes every other test here and then drops
      // three signals exactly when the machine deselects the transceiver.
      $display("C0-C2 -> A0-A2, independent of /OE");
      // Park the bus side at a defined level first.  A floating input is
      // outside both parts' operating conditions, and comparing two
      // indeterminate outputs is not a test of anything.
      na_en = 1; na_drv = 16'h0000; vw_en = 0;
      oe_n = 1;
      for (i = 0; i < 8; i = i + 1) begin
         c = i[2:0]; #200; check("c->a, oe_n=1");
      end
      oe_n = 0;
      for (i = 0; i < 8; i = i + 1) begin
         c = i[2:0]; #200; check("c->a, oe_n=0");
      end

      $display("");
      $display("%0d checks, %0d mismatches", checks, errors);
      if (errors == 0) $display("EQUIVALENT");
      else             $display("NOT EQUIVALENT");
      $finish(errors ? 1 : 0);
   end
endmodule
