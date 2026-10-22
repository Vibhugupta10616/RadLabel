# Sample patient (synthetic)

Five follow-up chest X-ray reports of one fictional patient, **written by hand for the website demo. They are not
Indiana University (Open-i) text** and contain no real patient data, so they are committed.

R1 small left effusion · R2 moderate effusion, mild cardiomegaly, basilar opacity "possibly atelectasis" · R3 new
pacemaker, stable moderate effusion, "infection cannot be excluded" · R4 decreasing small effusion, stable mild
cardiomegaly · R5 effusion resolved, borderline heart size.

`sample_results.json` holds their pipeline outputs, computed once through the real pipeline
(`python -m radlabel.api.sample`), so loading the sample on the website needs no LLM call. It is rebuilt only when
the texts change (their hash is stored); the pipeline and prompts are never tuned to produce particular badges.
