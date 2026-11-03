========================================================================
 GOW SBK TOOLS BY NICHO  -  v1.0
 SBK / SBP audio editor for God of War 1 & 2 (PS2) WAD files
========================================================================

WHAT IS IT?
A PC tool (runs on Windows and on Wine/Winlator) that edits the audio inside
God of War 1 and God of War 2 (PS2) WAD files: open a WAD, pick an SBK, then
play / export / replace a sound with your own WAV and SAVE.

PACKAGE CONTENTS
  Readme-Eng.txt         : these instructions (English)
  Information-Eng.txt    : what the tool can and cannot do
  Readme-Indo.txt / Informasi-Indo.txt      : Bahasa Indonesia version
  Leia-me-Br.txt / Informacoes-Br.txt       : Português (Brasil) version
  Katalog_SBK.txt        : list of every SBK/SBP with its sound names
  SBK Tools\             : the program folder (SBK_Tools.exe + support files)

IMPORTANT: do not move SBK_Tools.exe alone to another place. It needs the
DLLs and files next to it. Keep the WHOLE "SBK Tools" folder together.

QUICK START
  1. Get your .WAD files. This tool does NOT open PAK, TOC or ISO files.
     Extract the WAD from the PAK first with another tool (for example
     God of War Browser).
  2. Run SBK_Tools.exe. On the first launch you choose a language
     (Indonesia / English / Português). You can change it any time with
     the "Language" box in the main window.
  3. Click "Open WAD" and choose the WAD. If the file dialog misbehaves
     under Wine, paste the file location in the path box and click
     "Open path". Not sure which WAD holds a sound? Click "SBK catalog"
     and search by WAD / SBK / sound name.
  4. Select an SBK in the list and click "Edit audio" (or double-click it).
  5. Select a sample, then:
       Play           = hear the original sample
       Export WAV     = save the original sample as a WAV file
       Hear WAV       = listen to your WAV before inserting it
       Replace from WAV = replace the sample with your WAV
  6. Click SAVE in the main window. The edited result is written to the
     original WAD, and a copy of the untouched WAD is kept once as
     NAME.WAD.bak. Want the result in another file? Use "Save As".
  7. Put the edited WAD back into the game's PAK / ISO with another tool.

SAMPLE RATE
  - VAG banks: the original sample rate is read from the file; nothing to set.
  - Internal audio banks: the original rate is not stored in the file. The
    tool guesses 22050 Hz. Press Play; if it sounds too slow / too fast,
    change the "Sample rate" number until it sounds right, then use the same
    number when you Replace.

IF YOUR WAV IS LONGER THAN THE ORIGINAL SLOT
Pick a mode in the box "If the audio is longer than the slot":
  - Enlarge WAD : the audio is not cut; the WAD grows. The ISO must be
                  rebuilt and the game may crash if it grows too much.
                  For a small share of samples this mode is safely REFUSED
                  (the SBK header cannot be shifted safely) and the WAD is
                  left untouched. Use another mode for those samples.
  - Lower rate  : the WAD size stays the same; lower quality (VAG banks only).
  - Cut         : the WAD size stays the same; the extra audio is discarded.
A WAV shorter than the slot is always safe (the rest is filled with silence
and the WAD size does not change).

BEGINNER TIPS
  - Always work on a COPY. Keep your original PAK / ISO.
  - Change one thing per test, then try it in the game. Do not stack many
    changes at once; if it crashes you will not know the cause.
  - Start with a WAV shorter than the original (safest).

IF YOU FIND AN ERROR / BUG
The tool logs errors to  gow_tool_error.txt  (next to the exe) and shows its
location in the error window. Send that error text (or a photo of it) along
with the names of the WAD and SBK you opened to the tool's author.

WINLATOR / WINE
Use this folder version (not a single-file exe). If the window or the file
dialog misbehaves, use the path box + "Open path".

========================================================================
 Gow SBK Tools by Nicho
========================================================================
