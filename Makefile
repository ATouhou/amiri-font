.PHONY: all clean ttf web pack check

VERSION=0.101

TOOLS=tools
SRC=sources
WEB=web
DOC=documentation
TESTS=test-suite
FONTS=amiri-regular amiri-bold amiri-slanted
DOCS=README README-Arabic NEWS NEWS-Arabic

BUILD=$(TOOLS)/build.py
RUNTEST=$(TOOLS)/runtest.py
FF=python $(BUILD)
MKEOT=ttf2eot
MKWOFF=sfnt2woff

SFDS=$(FONTS:%=$(SRC)/%.sfdir)
DTTF=$(FONTS:%=%.ttf)
WTTF=$(FONTS:%=$(WEB)/%.ttf)
WOFF=$(FONTS:%=$(WEB)/%.woff)
EOTS=$(FONTS:%=$(WEB)/%.eot)
PDFS=$(DOC)/amiri-table.pdf
CSSS=$(WEB)/amiri.css
FEAT=$(wildcard $(SRC)/*.fea)
TEST=$(wildcard $(TESTS)/*.test)

DOCFILES=$(DOCS:%=$(DOC)/%.txt)
license=OFL.txt OFL-FAQ.txt

all: ttf web

ttf: $(DTTF)
web: $(WTTF) $(WOFF) $(EOTS) $(CSSS)
doc: $(PDFS)

$(WEB)/%.ttf: %.ttf $(BUILD)
	@echo "   FF\t$@"
	@mkdir -p $(WEB)
	@$(FF) --input $< --output $@ --web

%.ttf: $(SRC)/%.sfdir $(SRC)/%.fea $(FEAT) $(BUILD)
	@echo "   FF\t$@"
	@$(FF) --input $< --output $@ --desktop --feature-file $(<:%.sfdir=%.fea) --version $(VERSION) --no-localised-name

%-slanted.ttf: $(SRC)/%-regular.sfdir $(SRC)/%-regular.fea $(FEAT) $(BUILD)
	@echo "   FF\t$@"
	@$(FF) --input $< --output $@ --desktop --feature-file $(<:%.sfdir=%.fea) --version $(VERSION) --no-localised-name --slant=7

$(WEB)/%.woff: $(WEB)/%.ttf
	@echo "   FF\t$@"
	@mkdir -p $(WEB)
	@$(MKWOFF) $<

$(WEB)/%.eot: $(WEB)/%.ttf
	@echo "   FF\t$@"
	@mkdir -p $(WEB)
	@$(MKEOT) $< > $@

$(WEB)/%.css: $(WTTF) $(BUILD)
	@echo "   GEN\t$@"
	@mkdir -p $(WEB)
	@$(FF) --css --input "$(WTTF)" --output $@ --version $(VERSION)

$(DOC)/amiri-table.pdf: amiri-regular.ttf
	@echo "   GEN\t$@"
	@mkdir -p $(DOC)
	@fntsample --exclude-range 0x25A0-0x25FF --font-file $< --output-file $@.tmp --print-outline > $@.txt
	@pdfoutline $@.tmp $@.txt $@
	@rm -f $@.tmp $@.txt

check: $(TEST) $(DTTF)
ifeq ($(shell which hb-shape),)
	@echo "hb-shape not found, skipping tests"
else
	@echo "running tests"
	@$(RUNTEST) $(TEST)
endif

clean:
	rm -rfv $(DTTF) $(WTTF) $(WOFF) $(EOTS) $(CSSS) $(PDFS)

#->8-
PACK=$(SRC)/amiri-regular.sfd $(SRC)/amiri-bold.sfd

pack: $(PACK)

%.sfd: %.sfdir $(BUILD)
	@echo "   GEN\t$@"
	@$(FF) --sfd --input $< --output $@

distclean:
	@rm -rf amiri-$(VERSION) amiri-$(VERSION).tar.bz2
	@rm -rf $(PACK)

dist: all check pack doc
	@echo "   Making dist tarball"
	@mkdir -p amiri-$(VERSION)/$(SRC)
	@mkdir -p amiri-$(VERSION)/$(WEB)
	@mkdir -p amiri-$(VERSION)/$(DOC)
	@mkdir -p amiri-$(VERSION)/$(TOOLS)
	@mkdir -p amiri-$(VERSION)/$(TESTS)
	@cp $(PACK) amiri-$(VERSION)/$(SRC)
	@cp $(FEAT) amiri-$(VERSION)/$(SRC)
	@sed -e "/#->8-/,$$ d" -e "s/sfdir/sfd/" Makefile > amiri-$(VERSION)/Makefile
	@cp $(license) amiri-$(VERSION)
	@cp $(DTTF) amiri-$(VERSION)
	@cp README.txt amiri-$(VERSION)
	@cp $(DOCFILES) amiri-$(VERSION)/$(DOC)
	@cp $(WTTF) amiri-$(VERSION)/$(WEB)
	@cp $(WOFF) amiri-$(VERSION)/$(WEB)
	@cp $(EOTS) amiri-$(VERSION)/$(WEB)
	@cp $(CSSS) amiri-$(VERSION)/$(WEB)
	@cp $(WEB)/README amiri-$(VERSION)/$(WEB)
	@cp $(PDFS) amiri-$(VERSION)/$(DOC)
	@cp $(TEST) amiri-$(VERSION)/$(TESTS)
	@cp $(BUILD) amiri-$(VERSION)/$(TOOLS)
	@cp $(RUNTEST) amiri-$(VERSION)/$(TOOLS)
	@tar cfj amiri-$(VERSION).tar.bz2 amiri-$(VERSION)
