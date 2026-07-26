MAIN := AnonymousSubmission2027

LATEXMK ?= latexmk
LATEXMKFLAGS ?= -pdf -interaction=nonstopmode -halt-on-error -file-line-error

SOURCES := $(wildcard *.tex *.bib *.sty *.bst) \
	$(wildcard figures/*.pdf)

.PHONY: all watch clean distclean

all: $(MAIN).pdf

$(MAIN).pdf: $(SOURCES)
	$(LATEXMK) $(LATEXMKFLAGS) $(MAIN).tex

watch:
	$(LATEXMK) $(LATEXMKFLAGS) -pvc $(MAIN).tex

clean:
	$(LATEXMK) -c $(MAIN).tex

distclean:
	$(LATEXMK) -C $(MAIN).tex
