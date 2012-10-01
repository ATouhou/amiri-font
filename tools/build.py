#!/usr/bin/python
# coding=utf-8
#
# build.py - Amiri font build utility
#
# Written in 2010-2012 by Khaled Hosny <khaledhosny@eglug.org>
#
# To the extent possible under law, the author have dedicated all copyright
# and related and neighboring rights to this software to the public domain
# worldwide. This software is distributed without any warranty.
#
# You should have received a copy of the CC0 Public Domain Dedication along
# with this software. If not, see
# <http://creativecommons.org/publicdomain/zero/1.0/>.

# minimum required FontForge version
min_ff_version = "20120702"

import fontforge
import psMat
import sys
import os
import getopt
import math
from tempfile import mkstemp
from fontTools.ttLib import TTFont

def genCSS(font, base):
    """Generates a CSS snippet for webfont usage based on:
    http://www.fontspring.com/blog/the-new-bulletproof-font-face-syntax"""

    style = ("slanted" in font.fullname.lower()) and "oblique" or "normal"
    weight = font.os2_weight
    family = font.familyname + "Web"

    css = """
@font-face {
    font-family: %(family)s;
    font-style: %(style)s;
    font-weight: %(weight)s;
    src: url('%(base)s.eot?') format('eot'),
         url('%(base)s.woff') format('woff'),
         url('%(base)s.ttf')  format('truetype');
}
""" %{"style":style, "weight":weight, "family":family, "base":base}

    return css

def cleanAnchors(font):
    """Removes anchor classes (and associated lookups) that are used only
    internally for building composite glyph."""

    klasses = (
            "Dash",
            "DigitAbove",
            "DigitBelow",
            "DotAbove",
            "DotAlt",
            "DotBelow",
            "DotBelowAlt",
            "DotHmaza",
            "HamzaBelow",
            "HighHamza",
            "MarkDotAbove",
            "MarkDotBelow",
            "RingBelow",
            "RingDash",
            "Stroke",
            "TaaAbove",
            "TaaBelow",
            "Tail",
            "TashkilAboveDot",
            "TashkilBelowDot",
            "TwoDotsAbove",
            "TwoDotsBelow",
            "TwoDotsBelowAlt",
            "VAbove",
            )

    for klass in klasses:
        subtable = font.getSubtableOfAnchor(klass)
        lookup = font.getLookupOfSubtable(subtable)
        font.removeLookup(lookup)

def flattenNestedReferences(font, ref, new_transform=(1, 0, 0, 1, 0, 0)):
    """Flattens nested references by replacing them with the ultimate reference
    and applying any transformation matrices involved, so that the final font
    has only simple composite glyphs. This to work around what seems to be an
    Apple bug that results in ignoring transformation matrix of nested
    references."""

    name = ref[0]
    transform = ref[1]
    glyph = font[name]
    new_ref = []
    if glyph.references and glyph.foreground.isEmpty():
        for nested_ref in glyph.references:
            for i in flattenNestedReferences(font, nested_ref, transform):
                matrix = psMat.compose(i[1], new_transform)
                new_ref.append((i[0], matrix))
    else:
        matrix = psMat.compose(transform, new_transform)
        new_ref.append((name, matrix))

    return new_ref

def validateGlyphs(font):
    """Fixes some common FontForge validation warnings, currently handles:
        * wrong direction
        * flipped references
    In addition to flattening nested references."""

    wrong_dir = 0x8
    flipped_ref = 0x10
    for glyph in font.glyphs():
        state = glyph.validate(True)
        refs = []

        if state & flipped_ref:
            glyph.unlinkRef()
            glyph.correctDirection()
        if state & wrong_dir:
            glyph.correctDirection()

        for ref in glyph.references:
            for i in flattenNestedReferences(font, ref):
                refs.append(i)
        if refs:
            glyph.references = refs

def setVersion(font, version):
    font.version = "%07.3f" % float(version)
    for name in font.sfnt_names:
        if name[0] == "Arabic (Egypt)" and name[1] == "Version":
            font.appendSFNTName(name[0], name[1],
                                name[2].replace("VERSION", font.version.replace(".", "\xD9\xAB")))

def mergeFeatures(font, feafile):
    """Merges feature file into the font while making sure mark positioning
    lookups (already in the font) come after kerning lookups (from the feature
    file), which is required by Uniscribe to get correct mark positioning for
    kerned glyphs."""

    oldfea = mkstemp(suffix='.fea')[1]
    font.generateFeatureFile(oldfea)

    for lookup in font.gpos_lookups:
        font.removeLookup(lookup)

    font.mergeFeature(feafile)
    font.mergeFeature(oldfea)
    os.remove(oldfea)

def makeCss(infiles, outfile):
    """Builds a CSS file for the entire font family."""

    css = ""

    for f in infiles.split():
        base = os.path.splitext(os.path.basename(f))[0]
        font = fontforge.open(f)
        css += genCSS(font, base)
        font.close()

    out = open(outfile, "w")
    out.write(css)
    out.close()

def generateFont(font, outfile, hack=False):
    flags  = ("opentype", "dummy-dsig", "round", "omit-instructions")

    font.selection.all()
    font.correctReferences()
    font.selection.none()

    # fix some common font issues
    validateGlyphs(font)

    if hack:
        # ff takes long to write the file, so generate to tmp file then rename
        # it to keep fontview happy
        import subprocess
        tmpout = mkstemp(dir=".", suffix=os.path.basename(outfile))[1]
        font.generate(tmpout, flags=flags)
        #os.rename(tmpout, outfile) # file monitor will not see this, why?
        p = subprocess.Popen("cat %s > %s" %(tmpout, outfile), shell=True)
        p.wait()
        os.remove(tmpout)
    else:
        font.generate(outfile, flags=flags)
    font.close()

def drawOverUnderline(font, name, uni, glyphclass, pos, thickness, width):
    glyph = font.createChar(uni, name)
    glyph.width = 0
    glyph.glyphclass = glyphclass

    pen = glyph.glyphPen()

    pen.moveTo((-50, pos))
    pen.lineTo((-50, pos + thickness))
    pen.lineTo((width + 50, pos + thickness))
    pen.lineTo((width + 50, pos))
    pen.closePath()

    return glyph

def makeOverUnderline(font, over=True, under=True, o_pos=None, u_pos=None):
    # test string:
    # صِ̅فْ̅ ̅خَ̅ل̅قَ̅ ̅بًّ̅ صِ̲فْ̲ ̲خَ̲ل̲قَ̲ ̲بِ̲

    thickness = font.uwidth # underline width (thickness)
    minwidth = 100.0

    if not o_pos:
        o_pos = font.os2_typoascent

    if not u_pos:
        u_pos = font.upos - thickness # underline pos

    # figure out script/language spec used in other features in the font, we
    # will use them when creating our lookups
    script_lang = None
    for lookup in font.gsub_lookups:
        feature_info = font.getLookupInfo(lookup)[2]
        if feature_info and feature_info[0][0] == 'init':
            script_lang = tuple(feature_info[0][1])
            break

    assert(script_lang)

    # collect glyphs grouped by their widths rounded by 100 units, we will use
    # them to decide the widths of over/underline glyphs we will draw
    widths = {}
    for glyph in font.glyphs():
        if glyph.glyphclass == 'baseglyph':
            width = round(glyph.width/100) * 100
            width = width > minwidth and width or minwidth
            if not width in widths:
                widths[width] = []
            widths[width].append(glyph.glyphname)

    # first replace over/underline marks by a glyph with a 'baseglyph' class,
    # so that we can use can use it in contextual substitution while setting
    # 'ignore_marks' flag
    font.addLookup('mark hack', 'gsub_single', (), (('mark', script_lang),), font.gsub_lookups[-1])
    font.addLookupSubtable('mark hack', 'mark hack 1')

    if over:
        o_encoded = drawOverUnderline(font, 'uni0305', 0x0305, 'mark', o_pos, thickness, 500)
        o_base = drawOverUnderline(font, 'uni0305.0', -1, 'baseglyph', o_pos, thickness, 500)
        o_encoded.addPosSub('mark hack 1', o_base.glyphname)

    if under:
        u_encoded = drawOverUnderline(font, 'uni0332', 0x0332, 'mark', u_pos, thickness, 500)
        u_base = drawOverUnderline(font, 'uni0332.0', -1, 'baseglyph', u_pos, thickness, 500)

    context_lookup_name = 'OverUnderLine'
    font.addLookup(context_lookup_name, 'gsub_contextchain', ('ignore_marks'), (('mark', script_lang),), font.gsub_lookups[-1])

    for width in sorted(widths.keys()):
        # for each width group we create an over/underline glyph with the same
        # width, and add a contextual substitution lookup to use it when an
        # over/underline follows any glyph in this group

        single_lookup_name = str(width)

        font.addLookup(single_lookup_name, 'gsub_single', (), (), font.gsub_lookups[-1])
        font.addLookupSubtable(single_lookup_name, single_lookup_name + '1')

        if over:
            o_name = 'uni0305.%d' % width
            o_glyph = drawOverUnderline(font, o_name, -1, 'mark', o_pos, thickness, width)
            o_base.addPosSub(single_lookup_name + '1', o_name)

        if under:
            u_name = 'uni0332.%d' % width
            u_glyph = drawOverUnderline(font, u_name, -1, 'mark', u_pos, thickness, width)
            u_base.addPosSub(single_lookup_name + '1', u_name)

        context = "%s %s" %(over and o_base.glyphname or "", under and u_base.glyphname or "")

        rule = '| [%s] [%s] @<%s> | ' %(" ".join(widths[width]), context, single_lookup_name)

        font.addContextualSubtable(context_lookup_name, context_lookup_name + str(width), 'coverage', rule)

def centerGlyph(glyph):
    width = glyph.width
    glyph.right_side_bearing = glyph.left_side_bearing = (glyph.right_side_bearing + glyph.left_side_bearing)/2
    glyph.width = width

def buildLatinExtras(font, italic):
    for ltr, rtl in (("question", "uni061F"), ("radical", "radical.rtlm")):
        if ltr in font:
            font[rtl].clear()
            font[rtl].addReference(ltr, psMat.scale(-1, 1))
            font[rtl].left_side_bearing = font[ltr].right_side_bearing
            font[rtl].right_side_bearing = font[ltr].left_side_bearing

    # slanted arabic question mark
    if italic:
        question = font.createChar(-1, "uni061F.rtl")
        question.addReference("uni061F", italic)
        question.useRefsMetrics("uni061F")

    for name in ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"):
        if italic:
            # they are only used in Arabic contexts, so always reference the
            # italic rtl variant
            refname = name +".rtl"
        else:
            refname = name
        small = font.createChar(-1, name + ".small")
        small.clear()
        small.addReference(refname, psMat.scale(0.6))
        small.transform(psMat.translate(0, -40))
        small.width = 600
        centerGlyph(small)

        medium = font.createChar(-1, name + ".medium")
        medium.clear()
        medium.addReference(refname, psMat.scale(0.8))
        medium.transform(psMat.translate(0, 50))
        medium.width = 900
        centerGlyph(medium)

def mergeLatin(font, feafile, italic=False, glyphs=None, kerning=True):
    styles = {"Regular": "Roman",
              "Slanted": "Italic",
              "Bold": "Bold",
              "BoldSlanted": "BoldItalic"}

    style = styles[font.fontname.split("-")[1]]

    latinfile = "Crimson-%s.sfd" %style

    tmpfont = mkstemp(suffix=os.path.basename(latinfile))[1]
    latinfont = fontforge.open("sources/crimson/sources/%s" %latinfile)
    latinfont.em = 2048

    # convert to quadratic splines then simplify
    latinfont.is_quadratic = True
    for glyph in latinfont.glyphs():
        glyph.simplify()

    validateGlyphs(latinfont) # to flatten nested refs mainly

    if glyphs:
        latinglyphs = list(glyphs)
    else:
        # collect latin glyphs we want to keep
        latinglyphs = []

        # we want all glyphs in latin0-9 encodings
        for i in range(0, 9):
            latinfont.encoding = 'latin%d' %i
            for glyph in latinfont.glyphs("encoding"):
                if glyph.encoding <= 255:
                    if glyph.glyphname not in latinglyphs:
                        latinglyphs.append(glyph.glyphname)
                elif glyph.unicode != -1 and glyph.unicode <= 0x017F:
                    # keep also Unicode Latin Extended-A block
                    if glyph.glyphname not in latinglyphs:
                        latinglyphs.append(glyph.glyphname)
                elif glyph.unicode == -1 and '.prop' in glyph.glyphname:
                    # proportional digits
                    latinglyphs.append(glyph.glyphname)

        # keep ligatures too
        ligatures = ("f_b", "f_f_b",
                     "f_h", "f_f_h",
                     "f_i", "f_f_i",
                     "f_j", "f_f_j",
                     "f_k", "f_f_k",
                     "f_l", "f_f_l",
                     "f_f")

        # and Arabic romanisation characters
        romanisation = ("afii57929", "uni02BE", "uni02BE", "amacron", "uni02BE",
                "amacron", "eacute", "uni1E6F", "ccedilla", "uni1E6F", "gcaron",
                "ycircumflex", "uni1E29", "uni1E25", "uni1E2B", "uni1E96",
                "uni1E0F", "dcroat", "scaron", "scedilla", "uni1E63", "uni1E11",
                "uni1E0D", "uni1E6D", "uni1E93", "dcroat", "uni02BB", "uni02BF",
                "rcaron", "grave", "gdotaccent", "gbreve", "umacron", "imacron",
                "amacron", "amacron", "uni02BE", "amacron", "uni02BE",
                "acircumflex", "amacron", "uni1E97", "tbar", "aacute", "amacron",
                "ygrave", "agrave", "uni02BE", "aacute", "Amacron", "Amacron",
                "Eacute", "uni1E6E", "Ccedilla", "uni1E6E", "Gcaron",
                "Ycircumflex", "uni1E28", "uni1E24", "uni1E2A", "uni1E0E",
                "Dcroat", "Scaron", "Scedilla", "uni1E62", "uni1E10", "uni1E0C",
                "uni1E6C", "uni1E92", "Dcroat", "Rcaron", "Gdotaccent", "Gbreve",
                "Umacron", "Imacron", "Amacron", "Amacron", "Amacron",
                "Acircumflex", "Amacron", "Tbar", "Aacute", "Amacron", "Ygrave",
                "Agrave", "Aacute")

        # and some typographic characters
        typographic = ("uni2010", "uni2011", "figuredash", "endash", "emdash",
                "afii00208", "quoteleft", "quoteright", "quotesinglbase",
                "quotereversed", "quotedblleft", "quotedblright", "quotedblbase",
                "uni201F", "dagger", "daggerdbl", "bullet", "onedotenleader",
                "ellipsis", "uni202F", "perthousand", "minute", "second",
                "uni2038", "guilsinglleft", "guilsinglright", "uni203E",
                "fraction", "i.TRK", "minus", "uni2213", "radical", "uni2042")

        for l in (ligatures, romanisation, typographic):
            for name in l:
                if name not in latinglyphs:
                    latinglyphs.append(name)

    # keep any glyph referenced by previous glyphs
    for name in latinglyphs:
        if name in latinfont:
            glyph = latinfont[name]
            for ref in glyph.references:
                latinglyphs.append(ref[0])
        else:
            print 'Font ‘%s’ is missing glyph: %s' %(font.fontname, name)

    # remove everything else
    for glyph in latinfont.glyphs():
        if glyph.glyphname not in latinglyphs:
            latinfont.removeGlyph(glyph)

    # common characters that can be used in Arabic and Latin need to be handled
    # carefully in the slanted font so that right leaning italic is used with
    # Latin, and left leaning slanted is used with Arabic, using ltra and rtla
    # features respectively, for less OpenType savvy apps we make the default
    # upright so it works reasonably with bot scripts
    if italic:
        if "Bold" in style:
            upright = fontforge.open("sources/crimson/sources/Crimson-Bold.sfd")
        else:
            upright = fontforge.open("sources/crimson/sources/Crimson-Roman.sfd")
        upright.em = 2048

        shared = ("exclam", "quotedbl", "numbersign", "dollar", "percent",
                  "quotesingle", "parenleft", "parenright", "asterisk", "plus",
                  "slash", "colon", "semicolon", "less", "equal", "greater",
                  "question", "at", "bracketleft", "backslash", "bracketright",
                  "asciicircum", "braceleft", "bar", "braceright", "brokenbar",
                  "section", "copyright", "guillemotleft", "logicalnot",
                  "registered", "plusminus", "uni00B2", "uni00B3", "paragraph",
                  "uni00B9", "ordmasculine", "guillemotright", "onequarter",
                  "onehalf", "threequarters", "questiondown", "quoteleft",
                  "quoteright", "quotesinglbase", "quotereversed",
                  "quotedblleft", "quotedblright", "quotedblbase", "uni201F",
                  "dagger", "daggerdbl", "perthousand", "minute", "second",
                  "guilsinglleft", "guilsinglright", "fraction", "uni2213")

        digits = ("zero", "one", "two", "three", "four", "five", "six",
                  "seven", "eight", "nine")

        for name in shared:
            glyph = latinfont[name]
            glyph.glyphname += '.ltr'
            glyph.unicode = -1
            upright.selection.select(name)
            upright.copy()
            latinfont.createChar(upright[name].encoding, name)
            latinfont.selection.select(name)
            latinfont.paste()

            if not name + ".ara" in font:
                rtl = latinfont.createChar(-1, name + ".rtl")
                rtl.addReference(name, italic)
                rtl.useRefsMetrics(name)

        for name in digits:
            glyph = latinfont[name]
            glyph.glyphname += '.ltr'
            glyph.unicode = -1
            upright.selection.select(name)
            upright.copy()
            latinfont.createChar(upright[name].encoding, name)
            latinfont.selection.select(name)
            latinfont.paste()

            rtl = latinfont.createChar(-1, name + ".rtl")
            rtl.addReference(name, italic)
            rtl.useRefsMetrics(name)

        for name in digits:
            pname = name + ".prop"
            upright.selection.select(pname)
            upright.copy()
            latinfont.createChar(-1, pname)
            latinfont.selection.select(pname)
            latinfont.paste()

        for name in digits:
            pname = name + ".prop"
            rtl = latinfont.createChar(-1, name + ".rtl" + ".prop")
            rtl.addReference(pname, italic)
            rtl.useRefsMetrics(pname)

    # copy kerning classes
    kern_lookups = {}
    if kerning:
        for lookup in latinfont.gpos_lookups:
            kern_lookups[lookup] = {}
            kern_lookups[lookup]["subtables"] = []
            kern_lookups[lookup]["type"], kern_lookups[lookup]["flags"], dummy = latinfont.getLookupInfo(lookup)
            for subtable in latinfont.getLookupSubtables(lookup):
                if latinfont.isKerningClass(subtable):
                    kern_lookups[lookup]["subtables"].append((subtable, latinfont.getKerningClass(subtable)))

    for lookup in latinfont.gpos_lookups:
        latinfont.removeLookup(lookup)

    for lookup in latinfont.gsub_lookups:
        latinfont.removeLookup(lookup)

    latinfont.save(tmpfont)
    latinfont.close()

    font.mergeFonts(tmpfont)
    os.remove(tmpfont)

    buildLatinExtras(font, italic)

    for lookup in kern_lookups:
        font.addLookup(lookup,
                kern_lookups[lookup]["type"],
                kern_lookups[lookup]["flags"],
                (('kern',
                        (
                            ('DFLT', ('dflt',)),
                            ('latn', ('dflt', 'TRK ')),
                        )
                    ),)
                )

        for subtable in kern_lookups[lookup]["subtables"]:
            first = []
            second = []
            offsets = subtable[1][2]

            # drop non-existing glyphs
            for new_klasses, klasses in ((first, subtable[1][0]), (second, subtable[1][1])):
                for klass in klasses:
                    new_klass = []
                    if klass:
                        for name in klass:
                            if name in font:
                                new_klass.append(name)
                    new_klasses.append(new_klass)

            # if either of the classes is empty, don’t bother with the subtable
            if any(first) and any(second):
                font.addKerningClass(lookup, subtable[0], first, second, offsets)

def makeWeb(infile, outfile):
    """If we are building a web version then try to minimise file size"""

    # "short-post" generates a post table without glyph names to save some KBs
    # since glyph names are only needed for PDF's as readers use them to
    # "guess" characters when copying text, which is of little use in web fonts.
    flags = ("opentype", "short-post", "omit-instructions")

    font = fontforge.open(infile)

    # removed compatibility glyphs that of little use on the web
    compat_ranges = (
            (0xfb50, 0xfbb1),
            (0xfbd3, 0xfd3d),
            (0xfd50, 0xfdf9),
            (0xfdfc, 0xfdfc),
            (0xfe70, 0xfefc),
            )

    for glyph in font.glyphs():
        for i in compat_ranges:
            start = i[0]
            end = i[1]
            if start <= glyph.unicode <= end:
                font.removeGlyph(glyph)
                break

    tmpfont = mkstemp(suffix=os.path.basename(outfile))[1]
    font.generate(tmpfont, flags=flags)
    font.close()

    # now open in fontTools
    font = TTFont(tmpfont, recalcBBoxes=0)

    # our 'name' table is a bit bulky, and of almost no use in for web fonts,
    # so we strip all unnecessary entries.
    name = font['name']
    names = []
    for record in name.names:
        platID = record.platformID
        langID = record.langID
        nameID = record.nameID

        # we keep only en_US entries in Windows and Mac platform id, every
        # thing else is dropped
        if (platID == 1 and langID == 0) or (platID == 3 and langID == 1033):
            if nameID == 13:
                # the full OFL text is too much, replace it with a simple
                # string
                if platID == 3:
                    # MS strings are UTF-16 encoded
                    text = 'OFL v1.1'.encode('utf_16_be')
                else:
                    text = 'OFL v1.1'
                record.string = text
                names.append(record)
            # keep every thing else except Descriptor, Sample Text
            elif nameID not in (10, 19):
                names.append(record)

    name.names = names

    # FFTM is FontForge specific, remove it
    del(font['FFTM'])

    # force compiling GPOS/GSUB tables by fontTools, saves few tens of KBs
    for tag in ('GPOS', 'GSUB'):
        font[tag].compile(font)

    font.save(outfile)
    font.close()

    os.remove(tmpfont)

def makeSlanted(infile, outfile, feafile, version, slant):

    font = makeDesktop(infile, outfile, feafile, version, False, False)

    # compute amout of skew, magic formula copied from fontforge sources
    skew = psMat.skew(-slant * math.pi/180.0)

    font.selection.all()
    font.transform(skew)

    # fix metadata
    font.italicangle = slant
    font.fullname += " Slanted"
    if font.weight == "Bold":
        font.fontname = font.fontname.replace("Bold", "BoldSlanted")
        font.appendSFNTName("Arabic (Egypt)", "SubFamily", "عريض مائل")
        font.appendSFNTName("English (US)",   "SubFamily", "Bold Slanted")
    else:
        font.fontname = font.fontname.replace("Regular", "Slanted")
        font.appendSFNTName("Arabic (Egypt)", "SubFamily", "مائل")

    mergeLatin(font, feafile, skew)

    # we want to merge features after merging the latin font because many
    # referenced glyphs are in the latin font
    mergeFeatures(font, feafile)

    generateFont(font, outfile)

def makeQuran(infile, outfile, feafile, version):
    font = makeDesktop(infile, outfile, feafile, version, False, False)

    # fix metadata
    font.fontname = font.fontname.replace("-Regular", "Quran-Regular")
    font.familyname += " Quran"
    font.fullname += " Quran"

    digits = ("zero", "one", "two", "three", "four", "five", "six",
              "seven", "eight", "nine")

    mergeLatin(font, feafile, glyphs=digits, kerning=False)

    punct = ("period", "guillemotleft", "guillemotright", "braceleft", "bar",
             "braceright", "bracketleft", "bracketright", "parenleft",
             "parenright", "slash")

    for name in punct:
        glyph = font[name+".ara"]
        glyph.glyphname = name
        glyph.unicode = fontforge.unicodeFromName(name)

    mergeFeatures(font, feafile)

    # set font ascent to the highest glyph in the font so that waqf marks don't
    # get truncated
    # we could have set os2_typoascent_add and hhea_ascent_add, but ff makes
    # the offset relative to em-size in the former and font bounds in the
    # later, but we want both to be relative to font bounds
    ymax = 0
    for glyph in font.glyphs():
        bb = glyph.boundingBox()
        if bb[-1] > ymax:
            ymax = bb[-1]

    font.os2_typoascent = font.hhea_ascent = ymax

    overline_pos = font[0x06D7].boundingBox()[1]
    makeOverUnderline(font, under=False, o_pos=overline_pos)

    generateFont(font, outfile)

def makeDesktop(infile, outfile, feafile, version, latin=True, generate=True):
    font = fontforge.open(infile)

    if version:
        setVersion(font, version)

    # remove anchors that are not needed in the production font
    cleanAnchors(font)

    #makeOverUnderline(font)

    # sample text to be used by font viewers
    sample = 'صِفْ خَلْقَ خَوْدٍ كَمِثْلِ ٱلشَّمْسِ إِذْ بَزَغَتْ يَحْظَىٰ ٱلضَّجِيعُ بِهَا نَجْلَاءَ مِعْطَارِ.'

    for lang in ('Arabic (Egypt)', 'English (US)'):
        font.appendSFNTName(lang, 'Sample Text', sample)

    if latin:
        mergeLatin(font, feafile)

        # we want to merge features after merging the latin font because many
        # referenced glyphs are in the latin font
        mergeFeatures(font, feafile)

    if generate:
        generateFont(font, outfile, True)
    else:
        return font

def usage(extramessage, code):
    if extramessage:
        print extramessage

    message = """Usage: %s OPTIONS...

Options:
  --input=FILE          file name of input font
  --output=FILE         file name of output font
  --features=FILE       file name of features file
  --version=VALUE       set font version to VALUE
  --slant=VALUE         autoslant
  --css                 output is a CSS file
  --web                 output is web version

  -h, --help            print this message and exit
""" % os.path.basename(sys.argv[0])

    print message
    sys.exit(code)

if __name__ == "__main__":
# disable the check for now
#   if fontforge.version() < min_ff_version:
#       print "You need FontForge %s or newer to build Amiri fonts" %min_ff_version
#       sys.exit(-1)

    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:],
                "h",
                ["help", "input=", "output=", "features=", "version=", "slant=", "css", "web", "quran"])
    except getopt.GetoptError, err:
        usage(str(err), -1)

    infile = None
    outfile = None
    feafile = None
    version = None
    slant = False
    css = False
    web = False
    quran = False

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage("", 0)
        elif opt == "--input": infile = arg
        elif opt == "--output": outfile = arg
        elif opt == "--features": feafile = arg
        elif opt == "--version": version = arg
        elif opt == "--slant": slant = float(arg)
        elif opt == "--css": css = True
        elif opt == "--web": web = True
        elif opt == "--quran": quran = True

    if not infile:
        usage("No input file specified", -1)
    if not outfile:
        usage("No output file specified", -1)

    if css:
        makeCss(infile, outfile)
    elif web:
        makeWeb(infile, outfile)
    else:
        if not version:
            usage("No version specified", -1)
        if not feafile:
            usage("No features file specified", -1)

        if slant:
            makeSlanted(infile, outfile, feafile, version, slant)
        elif quran:
            makeQuran(infile, outfile, feafile, version)
        else:
            makeDesktop(infile, outfile, feafile, version)
