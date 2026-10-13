"""FWC common-name -> life form. Hand-built; judgement calls documented in the report."""
SUB = ["hydrilla","eelgrass","coontail","southern naiad","illinois pondweed","stonewort","musk-grass","green fanwort","milfoil",
       "slender pondweed","sago pondweed","widgeongrass","brazilian elodea","limnophila","needleleaf waternymph","submersed","marine naiad",
       "bladderwort","water-moss","mermaid weed","florida mudmidget","naiad"]
ALG = ["algae","lyngbya","chaetomorpha","enteromorpha","sea lettuce"]
FLT = ["water-lettuce","water fern","water-hyacinth","duckweed","watermeal","mosquito fern","mosquitofern","giant salvinia","floating fern","frog's-bit",
       "crested floating heart","floating bladderwort","water-shield","tussock","water-pennywort","spatterdock","yellow water-lily","fragrant water-lily",
       "american lotus","banana-lily","water-lily","floating","pennywort","a_tuss","tuss"]
WOODY_OR_NON = ["willow","bald cypress","elderberry","buttonbush","wax myrtle","red maple","trees","tree","land","shore","island","spoil","structure","pier or boat dock",
                "such as a fishing pier","berm","oak","palm","bay tree","pond apple","brazilian peppertree","chinese tallow","grape","dog fennel","dogfennel","goldenrod",
                "no_access","natreeline","naisland","naweather","saltbush","asters","morning-glory","fern","old world","oldworldfern","cinnamon","swamp","marsh","a_spoil","a_marsh","cata","peruviana","pandanus","spp_","bog-moss","sphagnum"]
def form(sp):
    s = sp.strip().lower()
    if not s: return None
    # order matters: bladderwort floating before submersed bladderwort
    if "floating bladderwort" in s: return "floating"
    for k in ALG:
        if k in s: return "algae"
    for k in FLT:
        if k in s and "bladderwort" not in s: return "floating"
    for k in SUB:
        if k in s: return "submersed"
    for k in WOODY_OR_NON:
        if s == k or k in s: return "other"
    return "emergent"
def point_class(species):
    fs = {form(x) for x in species.split(",") if x.strip()} - {None}
    if "floating" in fs: return "floating"          # floating / floating-leaved present (may co-occur with emergent)
    if "emergent" in fs: return "emergent"
    if "submersed" in fs: return "submersed"
    if "algae" in fs: return "algae"
    return "other"
