import time

from classifier import generate_training_data
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

t = time.perf_counter()
X, y = generate_training_data(100, 500, 42)
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

for weights in (None, "balanced"):
    m = LogisticRegression(solver="lbfgs", max_iter=2000, class_weight=weights).fit(Xtr, ytr)
    p = m.predict(Xte)
    acc = accuracy_score(yte, p)
    f1 = f1_score(yte, p, average="macro")
    print(f"class_weight={weights!r:10} accuracy={acc:.3f} macro_f1={f1:.3f}")

print(f"total {time.perf_counter() - t:.1f}s")