"""small numpy/scipy replacements for scikit-learn pieces (the research venv has no sklearn)."""
import numpy as np
from scipy.optimize import minimize


class Logit:
    """L2-regularised logistic regression, features standardised internally; decision_function(X)."""
    def __init__(self, C=1.0): self.C = C
    def fit(self, X, y):
        X = np.asarray(X, float); y = np.asarray(y, float)
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9; Z = (X - self.mu) / self.sd
        Z1 = np.column_stack([np.ones(len(Z)), Z])
        def f(w):
            s = Z1 @ w; p = 1 / (1 + np.exp(-np.clip(s, -30, 30)))
            ll = -(y * np.log(p + 1e-12) + (1 - y) * np.log(1 - p + 1e-12)).mean() + 0.5 / self.C * (w[1:] ** 2).sum() / len(y)
            g = Z1.T @ (p - y) / len(y); g[1:] += w[1:] / self.C / len(y)
            return ll, g
        self.w = minimize(f, np.zeros(Z1.shape[1]), jac=True, method="L-BFGS-B").x
        return self
    def decision_function(self, X):
        Z = (np.asarray(X, float) - self.mu) / self.sd
        return self.w[0] + Z @ self.w[1:]


class Isotonic:
    """non-decreasing PAV fit, linear interpolation, clipped outside the range"""
    def fit(self, x, y):
        o = np.argsort(x); x = np.asarray(x, float)[o]; y = np.asarray(y, float)[o]
        v, w, n = list(y), [1.0] * len(y), list(range(len(y)))
        vals, wts, cnt = [], [], []
        for yy in y:
            vals.append(yy); wts.append(1.0); cnt.append(1)
            while len(vals) > 1 and vals[-2] > vals[-1]:
                t = wts[-2] + wts[-1]; vals[-2:] = [(vals[-2] * wts[-2] + vals[-1] * wts[-1]) / t]; wts[-2:] = [t]; cnt[-2:] = [cnt[-2] + cnt[-1]]
        self.y = np.repeat(vals, cnt); self.x = x
        return self
    def predict(self, q): return np.interp(np.asarray(q, float), self.x, self.y)
