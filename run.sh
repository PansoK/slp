#for i in a b c d e; do python examples/mosei3waynorm.py --config configs_feedback/sigmoid.yaml; done
#for i in a b c d e; do python examples/mosei3waynorm.py --config configs_feedback/softmax.yaml; done
#for i in a b c d e; do python examples/mosei3waynorm.py --config configs_feedback/sum_sigmoid.yaml; done
for i in a b c d e; do python examples/mosei3waynorm.py --config configs_feedback/sum_softmax.yaml; done
for i in a b c d e; do python examples/mosei3waynorm.py --config configs_feedback/dot.yaml; done
#for i in a b c d e; do python examples/mosei3waynorm.py --config configs_feedback/rnn.yaml; done
#for i in a b c d e; do python examples/mosei3waynorm.py --config configs_feedback/full.yaml; done
#for i in a b c d e; do python examples/mosei3waynorm.py --config configs_feedback/sigmoid_self.yaml; done
#for i in a b c d e; do python examples/mosei3waynorm.py --config configs_feedback/sum_sigmoid_self.yaml; done
#for i in a b c d e; do python examples/mosei3waynorm.py --config configs_feedback/attention.yaml; done
