# Equivalence proof: the substitute against the original's own gate-array cells.
IVERILOG ?= iverilog
VVP      ?= vvp
BUILD    ?= build

RTL = rtl/lib_1801.v rtl/vp1_055_orig.v rtl/vp1_055_repl.v

.PHONY: check clean
check: $(BUILD)/tb_equiv
	@$(VVP) $(BUILD)/tb_equiv

$(BUILD)/tb_equiv: $(RTL) sim/tb_equiv.v
	@mkdir -p $(BUILD)
	@$(IVERILOG) -g2012 -o $@ $(RTL) sim/tb_equiv.v

clean:
	@rm -rf $(BUILD)
	@rm -f $(BUSTEST_IMG)

# The bus stress volume: adversarial patterns driven over the bus by disk I/O,
# because D22 is on the peripheral processor's side and a CPU-side test never
# reaches it.  See bustest/README.md.
PYTHON      ?= python3
BUSTEST_IMG ?= bustest.dsk

.PHONY: bustest bustest-check
bustest: $(BUSTEST_IMG)

$(BUSTEST_IMG): bustest/make_bustest.py
	@$(PYTHON) bustest/make_bustest.py -o $@

# The same argument as `mutants`, applied to a disk image written by code that
# has never been run against a real volume.
bustest-check:
	@$(PYTHON) bustest/make_bustest.py --self-test

# A test that cannot fail proves nothing.  Each mutant is a mistake that is one
# wire or one part number away from the real design, and each must be caught.
MUTANTS = MUTANT_INVERTING MUTANT_DIR MUTANT_C_GATED

.PHONY: mutants
mutants:
	@mkdir -p $(BUILD)
	@fail=0; for m in $(MUTANTS); do \
	   $(IVERILOG) -g2012 -D$$m -o $(BUILD)/mut_$$m $(RTL) sim/tb_equiv.v; \
	   if $(VVP) $(BUILD)/mut_$$m 2>/dev/null | grep -q "^EQUIVALENT"; then \
	      echo "  NOT CAUGHT  $$m"; fail=1; \
	   else \
	      echo "  caught      $$m"; \
	   fi; \
	done; \
	if [ $$fail -ne 0 ]; then echo "mutation check FAILED"; exit 1; fi; \
	echo "all mutants caught"
