// The built-in sample patient's report texts: made-up reports written by hand (not real patient data or IU text).
// A copy of data/sample/exam_*.txt in the repository root; tests/test_web_sample.py fails if they differ.
import exam1 from './sample/exam_1.txt?raw'
import exam2 from './sample/exam_2.txt?raw'
import exam3 from './sample/exam_3.txt?raw'
import exam4 from './sample/exam_4.txt?raw'
import exam5 from './sample/exam_5.txt?raw'

export const SAMPLE_FILES = [exam1, exam2, exam3, exam4, exam5].map((text, k) => ({ name: `exam_${k + 1}.txt`, text }))
