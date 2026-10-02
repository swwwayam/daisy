"""One model vocabulary for recommendations, training and the UI."""
from sklearn.ensemble import (AdaBoostClassifier, AdaBoostRegressor, ExtraTreesClassifier,
    ExtraTreesRegressor, GradientBoostingClassifier, GradientBoostingRegressor,
    HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor)
from sklearn.linear_model import ElasticNet, HuberRegressor, Lasso, LinearRegression, LogisticRegression, Ridge, SGDClassifier, SGDRegressor
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor


def scaled(estimator):
    return make_pipeline(StandardScaler(), estimator)


MODEL_FACTORY = {
    "logistic_regression": lambda: scaled(LogisticRegression(max_iter=1000, random_state=42)),
    "random_forest_classifier": lambda: RandomForestClassifier(random_state=42, n_jobs=1),
    "gradient_boosting_classifier": lambda: GradientBoostingClassifier(random_state=42),
    "knn_classifier": lambda: scaled(KNeighborsClassifier()),
    "svm_classifier": lambda: scaled(SVC(probability=True, random_state=42)),
    "decision_tree_classifier": lambda: DecisionTreeClassifier(random_state=42),
    "extra_trees_classifier": lambda: ExtraTreesClassifier(random_state=42, n_jobs=1),
    "hist_gradient_boosting_classifier": lambda: HistGradientBoostingClassifier(random_state=42),
    "adaboost_classifier": lambda: AdaBoostClassifier(random_state=42),
    "gaussian_naive_bayes": lambda: GaussianNB(),
    "sgd_classifier": lambda: scaled(SGDClassifier(loss="log_loss", max_iter=1000, random_state=42)),
    "mlp_classifier": lambda: scaled(MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=300, random_state=42)),
    "linear_regression": lambda: LinearRegression(),
    "random_forest_regressor": lambda: RandomForestRegressor(random_state=42, n_jobs=1),
    "gradient_boosting_regressor": lambda: GradientBoostingRegressor(random_state=42),
    "ridge_regression": lambda: scaled(Ridge()),
    "svm_regressor": lambda: scaled(SVR()),
    "decision_tree_regressor": lambda: DecisionTreeRegressor(random_state=42),
    "extra_trees_regressor": lambda: ExtraTreesRegressor(random_state=42, n_jobs=1),
    "hist_gradient_boosting_regressor": lambda: HistGradientBoostingRegressor(random_state=42),
    "adaboost_regressor": lambda: AdaBoostRegressor(random_state=42),
    "knn_regressor": lambda: scaled(KNeighborsRegressor()),
    "lasso_regression": lambda: scaled(Lasso(max_iter=2000, random_state=42)),
    "elastic_net_regression": lambda: scaled(ElasticNet(max_iter=2000, random_state=42)),
    "huber_regression": lambda: scaled(HuberRegressor(max_iter=500)),
    "sgd_regressor": lambda: scaled(SGDRegressor(max_iter=1000, random_state=42)),
    "mlp_regressor": lambda: scaled(MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=300, random_state=42)),
}
CLASSIFICATION_MODELS = list(MODEL_FACTORY)[:12]
REGRESSION_MODELS = list(MODEL_FACTORY)[12:]


def row_limit(name):
    if name.startswith(("svm_", "mlp_")):
        return 10000
    if name.startswith("knn_"):
        return 50000
    return 100000


def catalog(problem_type=None):
    return [{"name": name, "label": name.replace("_", " ").title(),
             "problem_type": "classification" if name in CLASSIFICATION_MODELS else "regression",
             "max_rows": row_limit(name), "automatic_scaling": name in {
                 "logistic_regression", "knn_classifier", "svm_classifier", "sgd_classifier", "mlp_classifier",
                 "ridge_regression", "svm_regressor", "knn_regressor", "lasso_regression", "elastic_net_regression",
                 "huber_regression", "sgd_regressor", "mlp_regressor"}}
            for name in MODEL_FACTORY if problem_type is None or (name in CLASSIFICATION_MODELS) == (problem_type == "classification")]
