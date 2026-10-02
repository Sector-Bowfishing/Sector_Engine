#!/bin/zsh
S=$CLARITY_RESEARCH_ROOT
cd $S/stage14 && $S/geo/bin/python analysis/tables14.py >/dev/null && $S/geo/bin/python analysis/fill14.py && \
$S/geo/bin/python $S/stage11/tools/md2html.py _print.md CURRENT_CLARITY_STAGE14_BLIND_CERTIFICATION.html "Current Clarity Stage 14: Blind Certification" && \
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu --no-pdf-header-footer --allow-file-access-from-files --print-to-pdf=CURRENT_CLARITY_STAGE14_BLIND_CERTIFICATION.pdf "file://$PWD/CURRENT_CLARITY_STAGE14_BLIND_CERTIFICATION.html" 2>/dev/null; ls -la CURRENT_CLARITY_STAGE14_BLIND_CERTIFICATION.*
