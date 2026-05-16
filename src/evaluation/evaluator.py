from itertools import chain
from collections import Counter
from decimal import Decimal, InvalidOperation


class Evaluator:

    # =========================================================
    # NORMALIZATION
    # =========================================================

    @staticmethod
    def normalize_cell(x):
        if x is None:
            return "null"

        x = str(x).strip()

        if x == "":
            return ""

        try:
            num = Decimal(x)

            # preserve integer cleanly
            if num == num.to_integral():
                return str(num.to_integral())

            return format(num.normalize(), "f").rstrip("0").rstrip(".") or "0"

        except InvalidOperation:
            return x.lower()

    @staticmethod
    def normalize_table(table):
        if not table:
            return []

        return [
            tuple(Evaluator.normalize_cell(c) for c in row)
            for row in table
        ]

    @staticmethod
    def flatten(table):
        return list(chain.from_iterable(table)) if table else []

    def _clip(self, x):
        return max(0.0, min(1.0, x))

    # =========================================================
    # CELL METRICS (FIXED: multiset-safe)
    # =========================================================

    def cell_precision(self, gt, pr):
        gt_c = Counter(self.flatten(gt))
        pr_c = Counter(self.flatten(pr))

        if not pr_c:
            return 0.0

        common = sum((gt_c & pr_c).values())
        return self._clip(common / sum(pr_c.values()))

    def cell_recall(self, gt, pr):
        gt_c = Counter(self.flatten(gt))
        pr_c = Counter(self.flatten(pr))

        if not gt_c:
            return 0.0

        common = sum((gt_c & pr_c).values())
        return self._clip(common / sum(gt_c.values()))

    # =========================================================
    # TUPLE METRICS
    # =========================================================

    def tuple_cardinality(self, gt, pr):
        if not gt and not pr:
            return 1.0
        if not gt or not pr:
            return 0.0

        return self._clip(min(len(gt), len(pr)) / max(len(gt), len(pr)))


    # FROM QATCH
    def tuple_constraint(self, gt, pr):
        if not gt and not pr:
            return 1.0
        if not gt or not pr:
            return 0.0
        def sort_key(x):
            if x is None:
                return (0, '')
            elif isinstance(x, (int, float)):
                return (1, float(x))
            else:
                return (2, str(x))


        def sort_with_different_types(arr):
            return sorted(arr, key=sort_key)

        gt = [tuple(sort_with_different_types(row)) for row in gt]
        pr = [tuple(sort_with_different_types(row)) for row in pr]

        gt_c = Counter(gt)
        pr_c = Counter(pr)

        cardinality = [
            pr_c.get(key, 0) == count
            for key, count in gt_c.items()
        ]

        return round(sum(cardinality) / len(cardinality), 3)

    def tuple_order(self, target, prediction):
        if len(target) == 0 and len(prediction) == 0:
            return 1.0

        if len(target) == 0 or len(prediction) == 0:
            return 0.0

        new_target = []
        for t in target:
            if t in prediction and t not in new_target:
                new_target.append(t)

        new_pred = []
        for p in prediction:
            if p in target and p not in new_pred:
                new_pred.append(p)

        if len(new_target) == 0:
            rho = 0.0
        else:
            target_ranks = list(range(len(new_target)))
            pred_ranks = [new_target.index(x) for x in new_pred]

            diff_sq = 0
            for a, b in zip(target_ranks, pred_ranks):
                diff_sq += (a - b) ** 2

            n = len(new_target)
            if n < 2:
                n = 2

            rho = 1 - (6 * diff_sq) / (n * (n**2 - 1))
            rho = round(rho, 3)

        return (rho + 1) / 2

    # =========================================================
    # ENTRY POINT
    # =========================================================

    def evaluate(self, gt, pr):
        gt = self.normalize_table(gt)
        pr = self.normalize_table(pr)

        return {
            "cell_precision": self.cell_precision(gt, pr),
            "cell_recall": self.cell_recall(gt, pr),
            "tuple_cardinality": self.tuple_cardinality(gt, pr),
            "tuple_constraint": self.tuple_constraint(gt, pr),
            "tuple_order": self.tuple_order(gt, pr)
        }