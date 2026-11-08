========================================================================
 GOW SBK TOOLS BY NICHO  -  v1.1
 SBK / SBP audio editor for God of War 1 & 2 (PS2) WAD files
========================================================================

PACKAGE CONTENTS
  Readme-Eng.txt         : these instructions (English)
  Information-Eng.txt    : what the tool can and cannot do
  Readme-Indo.txt / Informasi-Indo.txt      : Bahasa Indonesia version
  Leia-me-Br.txt / Informacoes-Br.txt       : Português (Brasil) version
  Katalog_SBK.txt        : list of every SBK/SBP with its sound names
  SBK Tools\             : the program folder (SBK_Tools.exe + support files)

IMPORTANT: do not move SBK_Tools.exe alone to another place. It needs the
DLLs and files next to it. Keep the WHOLE "SBK Tools" folder together.

WHAT IS IT?
A PC tool (Windows and Wine/Winlator) that edits the audio inside God of War 1 and God of
War 2 (PS2) WAD files. Open the game ISO (or a single WAD, or a folder of WADs), pick an SBK,
then play / export / replace a sound with your own WAV and SAVE.

QUICK START
  1. Run SBK_Tools.exe. On the first launch you choose a language (Indonesia / English /
     Português); you can change it any time with the "Language" box.
  2. Open a source:
       Open ISO         : reads a God of War 1 or 2 ISO. Click the > next to PART1.PAK /
                          PART2.PAK to list the WADs (read through GODOFWAR.TOC in the ISO).
                          Only WADs that hold sounds are shown; VPK, VAG, PSS/PSW files and
                          WADs without an SBK are hidden.
       Open WAD         : opens a single loose .WAD file.
       Open WAD folder  : lists every .WAD in a folder.
     If the file dialog misbehaves under Wine, paste the file location (.iso or .wad) in the
     path box and click "Open path". Not sure which WAD holds a sound? Click "SBK catalog",
     search, then "Open this WAD" (if the ISO is open, the tool jumps straight to that WAD).
  3. Click a WAD in the "Source" tree (left); its SBK list appears on the right.
  4. Select an SBK and click "Edit audio" (or double-click it).
  5. Select a sample, then:
       Play             = hear the original sample
       Export WAV       = save the original sample as a WAV file
       Hear WAV         = listen to your WAV before inserting it
       Replace from WAV = replace the sample with your WAV
  6. Click SAVE in the main window:
       Loose WAD : the result is written to the original file; a copy of the untouched WAD
                   is kept once as NAME.WAD.bak.
       From ISO  : the WAD is written straight into the ISO, at EVERY copy location, and the
                   original content is saved in NAME.iso.sbkbak. The "Restore ISO" button
                   recovers everything.
     "Save As" writes the selected WAD to another file.

SAMPLE RATE
  - VAG banks: the original sample rate is read from the file; nothing to set.
  - Internal audio banks: the original rate is not stored in the file. The tool guesses
    22050 Hz. Press Play; if it sounds too slow / too fast, change the "Sample rate" number
    until it sounds right, then use the same number when you Replace.

IF YOUR WAV IS LONGER THAN THE ORIGINAL SLOT
Pick a mode in the box "If the audio is longer than the slot":
  - Enlarge WAD : the audio is not cut; the WAD grows. Only for LOOSE WADs (not available for
                  WADs from an ISO, because a WAD inside an ISO must keep its size). For a
                  small share of samples this mode is safely REFUSED (the SBK header cannot
                  be shifted safely) and the WAD is left untouched.
  - Lower rate  : the WAD size stays the same; lower quality (VAG banks only).
  - Cut         : the WAD size stays the same; the extra audio is discarded.
A WAV shorter than the slot is always safe (the rest is filled with silence; WAD size unchanged).

ISO NOTES
  - GoW 1 lists the same WAD in several places (PART1 and PART2), and GoW 2 also stores some
    WADs in more than one copy. The tool writes every copy so they stay consistent.
  - Before writing, the tool checks the WAD marker at each location; if one does not match,
    nothing is written.
  - Work on a COPY of the ISO, and close other programs that use that ISO.

BEGINNER TIPS
  - Always work on a COPY. Keep your original ISO.
  - Change one thing per test, then try it in the game. Do not stack many changes.
  - Start with a WAV shorter than the original (safest).

IF YOU FIND AN ERROR / BUG
The tool logs errors to gow_tool_error.txt (next to the exe) and shows its location in the
error window. Send that error text (or a photo of it) with the names of the WAD and SBK you opened.

WINLATOR / WINE
Use this folder version (not a single-file exe). If the window or the file dialog misbehaves,
use the path box + "Open path".

========================================================================
 Gow SBK Tools by Nicho
========================================================================
