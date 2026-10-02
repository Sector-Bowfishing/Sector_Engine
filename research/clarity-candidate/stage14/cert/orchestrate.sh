#!/bin/zsh
# value-blind hand-offs: NLA ACOLITE -> SYKE ACOLITE; WQP extraction -> finalize -> tasks -> WQP ACOLITE
cd $CLARITY_RESEARCH_ROOT/stage14/cert
(
  until grep -q CERT_ACO_DONE aco_nla_a1b.log; do sleep 30; done
  echo "$(date) NLA ACOLITE done; starting SYKE" >> orchestrate.log
  $CLARITY_RESEARCH_ROOT/geo/bin/python run_cert_aco_a1.py tasks_syke.json $CLARITY_RESEARCH_ROOT/stage14/cert/res_ns --workers 4 > aco_syke.log 2>&1
  echo "$(date) SYKE ACOLITE done" >> orchestrate.log
) &
(
  until grep -q "^finished" ex_wqp_a2_c1.log && grep -q "^finished" ex_wqp_a2_legacy.log; do sleep 30; done
  echo "$(date) WQP extraction done; finalizing" >> orchestrate.log
  $CLARITY_RESEARCH_ROOT/geo/bin/python finalize_wqp.py > finalize_wqp.log 2>&1
  $CLARITY_RESEARCH_ROOT/geo/bin/python build_tasks.py wqp_sample.csv tasks_wqp.json out_wqp_c1.csv out_wqp_legacy.csv >> finalize_wqp.log 2>&1
  echo "$(date) WQP tasks built; starting WQP ACOLITE" >> orchestrate.log
  $CLARITY_RESEARCH_ROOT/geo/bin/python run_cert_aco_a1.py tasks_wqp.json $CLARITY_RESEARCH_ROOT/stage14/cert/res_wqp --workers 6 > aco_wqp.log 2>&1
  echo "$(date) WQP ACOLITE done" >> orchestrate.log
) &
wait
echo "$(date) ALL_DONE" >> orchestrate.log
