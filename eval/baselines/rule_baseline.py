"""Rule baseline (README §6.2): the pipeline's rule labeller, unchanged. The logic lives in
`radlabel.labelling.rules` (it reads no expert codes), so the pipeline's recall scan and normal check (M7) can reuse
it without importing from eval/.
"""

from radlabel.labelling.rules import label_report

__all__ = ["label_report"]
