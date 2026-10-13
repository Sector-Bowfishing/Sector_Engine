"""Build UMN taxon -> life-form lookup (hand-curated; every decision in the CSV). Run with cwd = umn_sfwmd/.
Classes: FLOATING_LEAVED, FREE_FLOATING, EMERGENT, SUBMERSED, ALGAE, MOSS_LIVERWORT (submersed), SHORELINE_WOODY, TERRESTRIAL_FORB, AMBIGUOUS_GENUS, NONTAXON
surface_tier: STRICT (headline surface truth) | INCLUSIVE (added in the inclusive sensitivity) | NO
canopy_capable: submersed taxa that can top out to the surface (reported separately, never counted as surface truth)."""
import json,csv,re
cnt=dict(json.load(open('out/taxa_counts.json')))
R={}  # taxon(lower) -> (class, tier, canopy, conf, rationale)
def add(names,cls,tier,canopy,conf,why):
    for n in names.split('|'): R[n.strip().lower()]=(cls,tier,canopy,conf,why)
FL,FF,EM,SU='FLOATING_LEAVED','FREE_FLOATING','EMERGENT','SUBMERSED'
add('Nymphaea odorata|nymphaea|Nuphar variegata|nuphar|Nuphar advena|Nuphar microphylla|Brasenia schreberi|Nelumbo lutea|Nymphaea tuberosa|nymphaeaceae',FL,'STRICT','N','high','rooted floating-leaved lily/lotus/watershield: leaves lie on the surface')
add('Potamogeton natans|Potamogeton nodosus|Sparganium natans|sparganium (floating)|Sparganium fluctuans',FL,'STRICT','N','high' ,'floating-leaved pondweed / floating-leaved bur-reed form (leaves float at surface)')
add('Persicaria amphibia|Polygonum amphibium|persicaria|Persicaria lapathifolia',FL,'INCLUSIVE','N','medium','amphibious smartweed: floating-leaved when aquatic, but also terrestrial form on shore; genus-level "persicaria" may be terrestrial')
add('Lemna minor|Lemna turionifera|lemna|Spirodela polyrhiza|Wolffia columbiana|wolffia|Wolffia borealis',FF,'STRICT','N','medium','free-floating duckweed/watermeal on the surface (often tiny, patchy, wind-driven; 10 m pixel detection is doubtful)')
add('Ricciocarpos natans',FF,'INCLUSIVE','N','low','free-floating liverwort, rare, tiny')
add('Riccia fluitans|riccia',SU,'NO','N','low','floating/submersed liverwort mats; treated submersed (conservative)')
add('Zizania palustris|zizania',EM,'STRICT','N','high','wild rice: emergent (aerial leaves) in summer, floating-leaved earlier; dense stands reach the surface')
add('Typha angustifolia|typha|Typha latifolia|Typha glauca',EM,'STRICT','N','high','cattail: tall emergent')
add('Schoenoplectus acutus|Schoenoplectus tabernaemontani|Schoenoplectus pungens|Schoenoplectus americanus|Schoenoplectus x oblongus|Scirpus validus|Bolboschoenus fluviatilis|Bolboschoenus maritimus|Scirpus cyperinus|Scirpus atrovirens',EM,'STRICT','N','high','bulrush: tall emergent')
add('schoenoplectus|scirpus',EM,'STRICT','N','medium','genus-level bulrush; mostly S. acutus/tabernaemontani in MN lakes but could include submersed S. subterminalis (listed separately)')
add('Schoenoplectus subterminalis',SU,'NO','N','high','water bulrush: submersed, floating-leaved only rarely')
add('Pontederia cordata',EM,'STRICT','N','high','pickerelweed: emergent')
add('Sparganium eurycarpum|Sparganium americanum|sparganium (emergent)|Sparganium emersum|Sparganium angustifolium',EM,'STRICT','N','medium','bur-reed emergent form (emersum/angustifolium also have floating/submersed strap leaves; counted emergent where labelled)')
add('sparganium',EM,'INCLUSIVE','N','low','genus-level bur-reed; emergent or floating or submersed strap leaves unknown')
add('Sagittaria latifolia|Sagittaria rigida|Sagittaria cuneata|Sagittaria cristata',EM,'STRICT','N','medium','arrowhead species with emergent leaves (rigida/cuneata can be submersed in deep water)')
add('Sagittaria graminea',EM,'INCLUSIVE','N','low','grass-leaved arrowhead: often a submersed ribbon-leaf form in lakes')
add('sagittaria',EM,'INCLUSIVE','N','low','genus-level arrowhead: emergent or submersed ribbon-leaf unknown')
add('Phragmites australis|Phalaris arundinacea|Butomus umbellatus|Glyceria borealis|Scolochloa festucacea|poaceae|Leersia oryzoides',EM,'INCLUSIVE','N','medium','tall emergent/shoreline grass; usually in or at the shore band (inclusive tier because commonly shoreline wet meadow)')
add('Dulichium arundinaceum|Iris versicolor|iris|Iris virginica|Calla palustris|Acorus americanus|acorus|Calamagrostis canadensis|Lythrum salicaria|Sium suave|Cicuta|cicuta',EM,'INCLUSIVE','N','low','emergent/shoreline herb, mostly at the water edge; not a 10 m open-water canopy')
add('equisetum|Equisetum fluviatile',EM,'INCLUSIVE','N','medium','water horsetail: emergent, sparse stems')
add('Eleocharis palustris|Eleocharis smallii|Eleocharis erythropoda',EM,'INCLUSIVE','N','medium','spikerush, emergent but sparse/low')
add('eleocharis',EM,'NO','N','low','genus-level; Eleocharis acicularis (submersed) dominates this genus in MN lakes; not counted')
add('Eleocharis acicularis',SU,'NO','N','high','needle spikerush: submersed turf')
add('carex|Carex pellita|Carex comosa|Carex scoparia|Carex aquatilis|Carex lacustris|cyperaceae|Juncus pelocarpus|juncus|Juncus arcticus|Juncus canadensis|Juncus effusus',EM,'NO','N','low','sedge/rush at shoreline or wet meadow; low and in the shore band; excluded from strict and inclusive (Eriocaulon is submersed)')
add('Hippuris vulgaris',SU,'NO','N','low','mare\'s-tail: submersed in lakes, emergent only in shallows; not counted')
add('Menyanthes trifoliata|Ranunculus flammula|Potentilla palustris|Alisma triviale|alisma|Caltha palustris|Rumex orbiculatus|Lysimachia terrestris|lysimachia|Boltonia asteroides|Asclepias incarnata|Eupatorium perfoliatum|Eupatorium dubium|Eupatorium maculatum|eutrochium|Impatiens capensis|impatiens|Lycopus americanus|Scutellaria lateriflora|scutellaria|solidago|verbena|bidens|Veronica americana|Nasturtium officinale|Triadenum fraseri|hypericum|Hypericum ellipticum|Asteraceae|lamiaceae|eragrostis|Lobelia dortmanna|Littorella uniflora','TERRESTRIAL_FORB','NO','N','medium','wet-meadow / shoreline forb: not an aquatic canopy; excluded')
add('salix|alnus|Betula pumila|Chamaedaphne calyculata|Myrica gale|Andromeda polifolia|Andromeda glaucophylla|Ledum groenlandicum','SHORELINE_WOODY','NO','N','high','shrub/tree at shore: excluded by task definition')
add('sphagnum','MOSS_LIVERWORT','NO','N','high','bog moss; excluded')
add('chara|Chara globularis|Chara canescens|characeae|nitella|Nitellopsis obtusa|Lychnothamnus barbatus|Tolypella intricata','ALGAE','NO','N','high','charophyte macroalgae: submersed, excluded as algae')
# SUBMERSED canopy-capable
add('Ceratophyllum demersum|ceratophyllum|Myriophyllum spicatum|Potamogeton crispus|Stuckenia pectinata|stuckenia|Potamogeton zosteriformis|Potamogeton praelongus|Potamogeton richardsonii|Potamogeton amplifolius|Potamogeton illinoensis|Potamogeton robbinsii|Myriophyllum sibiricum|Myriophyllum exalbescens|Elodea canadensis|elodea|Elodea nuttallii|Heteranthera dubia|zosterella|potamogeton (broad)|potamogeton|Potamogeton gramineus|Potamogeton epihydrus|Potamogeton vaseyi|Potamogeton alpinus|Potamogeton strictifolius|Potamogeton hillii|myriophyllum|Myriophyllum verticillatum|Myriophyllum alterniflorum|Utricularia vulgaris|Vallisneria americana',SU,'NO','Y','medium','submersed; can form a surface-topped canopy in late summer (milfoil, curlyleaf, coontail, pondweeds); reported separately as "canopy-capable submersed", never as surface truth (no per-point canopy flag in this release for fleet lakes)')
add('Najas flexilis|Najas guadalupensis|najas|Najas minor|potamogeton (narrow)|Potamogeton friesii|Potamogeton pusillus|Potamogeton foliosus|Potamogeton spirillus|Potamogeton obtusifolius|Stuckenia filiformis|Bidens beckii|Zannichellia palustris|Lemna trisulca|utricularia|Utricularia minor|Utricularia intermedia|Utricularia gibba|Utricularia macrorhiza|ranunculus|Ranunculus aquatilis|Ranunculus longirostris|Ranunculus flabellaris|Myriophyllum tenellum|isoetes|Isoetes echinospora|Fontinalis antipyretica|Fontinalis sullivantii|drepanocladus|Drepanocladus aduncus|Scorpidium scorpioides|callitriche|elatine|Elatine minima|Eriocaulon aquaticum|Myriophyllum farwellii',SU,'NO','N','high','submersed (incl. Lemna trisulca, which floats below the surface, and bladderworts, mosses); not surface-reaching')
add('Protectedspecies 1|Protectedspecies 2|Protectedspecies 3|Protectedspecies 4|Protectedspecies 5|Protectedspecies 6|Protectedspecies 7|Protectedspecies 8|Protectedspecies 9|Protectedspecies 10|Protectedspecies 11|Protectedspecies 12','NONTAXON','NO','N','high','de-identified protected species; life form unknown; point ignored for class assignment')
rows=[];miss=[]
for t,n in sorted(cnt.items(),key=lambda x:-x[1]):
    k=t.strip().lower()
    if k=='' : continue
    if k not in R: miss.append(t); continue
    c,tier,can,conf,why=R[k]; rows.append([t,n,c,tier,can,conf,why])
unused=[k for k in R if k not in {t.strip().lower() for t in cnt}]
print('unmapped',miss); print('rules for taxa not in data',unused)
with open('out/umn_taxon_lifeform_lookup.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['taxon','n_rows','life_form','surface_tier','canopy_capable_submersed','confidence','rationale']); w.writerows(rows)
import collections
print(collections.Counter((r[2],r[3]) for r in rows))
