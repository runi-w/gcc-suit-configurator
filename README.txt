GCC HOUSE MODEL — configurator base renders
Chosen 2026-07-18: clean-cut American aspirational model (Proper Cloth / Suitsupply style),
straight-on studio front, plain white background. Wholly synthetic (rights-clean).
Generated with Google Gemini 3 Pro Image.

renders/       flat plain-GREY suit render per garment CUT (front view). Fabric is composited on
               top of these in the configurator; each cut = one render (fabric-independent).
  front_2button_notch.png   DEFAULT — single-breasted, 2-button, notch lapel
  front_2button_peak.png    single-breasted, 2-button, PEAK lapel
  front_doublebreasted.png  double-breasted, peak lapel (6x2)
  front_3piece_vest.png     three-piece (2-button notch jacket + waistcoat)

drape_maps/    grayscale DRAPE MAP + alpha suit mask (LA PNG) extracted from each render.
               This is what the compositor multiplies each fabric through.

NOTE — 1-button cut: Gemini refuses to render a grey business suit as single-button (it forces a
2nd button every time; confirmed across 5 generations). A true 1-button needs a quick manual
retouch (remove the lower button in Photoshop) or should be offered only on tuxedo/formal cloths.
The peak-lapel render above is a clean, legitimate 2-button peak option in the meantime.
