"""Optional NB/BYM2 posterior fits with explicitly scaled, component-wise ICAR effects."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np

from app.config.underserved import UNDERSERVED_CONFIG
from app.services.underserved import blockers, validate_cohort


def scaled_icar_basis(ward_ids, edges):
    if len(set(ward_ids)) != len(ward_ids):
        raise ValueError("Graph has duplicate identifiers")
    if not ward_ids or any(not isinstance(ward, str) or not ward for ward in ward_ids):
        raise ValueError("Graph requires non-empty ward identifiers")
    lookup = {ward: i for i, ward in enumerate(ward_ids)}
    adjacency = np.zeros((len(ward_ids), len(ward_ids)))
    seen_edges = set()
    for first, second in edges:
        if first not in lookup or second not in lookup or first == second:
            raise ValueError("Unknown vertex or self-loop in adjacency")
        edge = tuple(sorted((first, second)))
        if edge in seen_edges:
            raise ValueError("Duplicate edge in adjacency graph")
        seen_edges.add(edge)
        i, j = lookup[first], lookup[second]
        adjacency[i, j] = adjacency[j, i] = 1
    components, unseen = [], set(range(len(ward_ids)))
    while unseen:
        stack, component = [min(unseen)], []
        while stack:
            i = stack.pop()
            if i not in unseen:
                continue
            unseen.remove(i)
            component.append(i)
            stack.extend(j for j in np.flatnonzero(adjacency[i]) if j in unseen)
        components.append(sorted(component))
    columns = []
    for component in components:
        if len(component) == 1:
            column = np.zeros(len(ward_ids))
            column[component[0]] = 1  # Singleton gets unit Normal, not an undefined ICAR prior.
            columns.append(column)
            continue
        weights = adjacency[np.ix_(component, component)]
        precision = np.diag(weights.sum(axis=1)) - weights
        eigenvalues, eigenvectors = np.linalg.eigh(precision)
        positive = eigenvalues > 1e-9
        raw_basis = eigenvectors[:, positive] / np.sqrt(eigenvalues[positive])
        scaling = math.exp(np.log(np.sum(raw_basis**2, axis=1)).mean())
        basis = raw_basis / math.sqrt(scaling)
        for k in range(basis.shape[1]):
            column = np.zeros(len(ward_ids))
            column[component] = basis[:, k]
            columns.append(column)
    return np.column_stack(columns) if columns else np.zeros((len(ward_ids), 0))


def fit_count_model(
    areas,
    edges=(),
    variant="NB",
    config=UNDERSERVED_CONFIG,
    holdout_ids=(),
    graph_review=None,
):
    """Reference mean excludes fitted area effects; never estimates hidden demand/reporting."""
    validate_cohort(areas, config)
    if not config.minimum_areas <= len(areas) <= config.max_model_areas:
        raise ValueError("Cohort outside configured model size bounds")
    if any(blockers(a, config) for a in areas):
        raise ValueError("Invalid model cohort")
    if variant not in ("NB", "BYM2", "BYM2_SHRINKAGE"):
        raise ValueError("Unknown model variant")
    if config.bym2_likelihood not in ("negative_binomial", "poisson"):
        raise ValueError(f"Unknown BYM2 likelihood: {config.bym2_likelihood}")
    likelihood = "negative_binomial" if variant == "NB" else config.bym2_likelihood
    ids = [a.ward_id for a in areas]
    if not holdout_ids:
        raise ValueError("Held-out areas are required; in-sample scores cannot flag candidates")
    if len(set(holdout_ids)) != len(holdout_ids) or not set(holdout_ids) <= set(ids):
        raise ValueError("Unknown or duplicate holdout identifier")
    training = [i for i, ward in enumerate(ids) if ward not in holdout_ids]
    if len(training) < config.minimum_areas - 1:
        raise ValueError("Insufficient training areas after holdout")
    covariates = np.array([[a.wad, a.non_tap_share] for a in areas])
    # Fit transformations on training areas only; held-out counts do not influence priors/scaling.
    mean, scale = covariates[training].mean(axis=0), covariates[training].std(axis=0)
    if np.any(scale < 1e-8):
        raise ValueError("Constant need-side covariate")
    design = (covariates - mean) / scale
    if np.linalg.matrix_rank(np.column_stack([np.ones(len(training)), design[training]])) < 3:
        raise ValueError("Collinear need-side covariates")
    exposure = np.array([a.households * a.period_months for a in areas])
    y = np.array([a.bookings for a in areas])
    if y[training].sum() == 0:
        raise ValueError("All-zero training counts cannot support a relative reference")
    if variant != "NB":
        if not edges:
            raise ValueError("Spatial variant requires a supplied, reviewed adjacency graph")
        if (
            not isinstance(graph_review, dict)
            or graph_review.get("status") != "REVIEWED"
            or graph_review.get("geography_version") != config.geography_version
            or not isinstance(graph_review.get("reviewer"), str)
            or not graph_review["reviewer"].strip()
            or not isinstance(graph_review.get("source_sha256"), str)
            or len(graph_review["source_sha256"]) != 64
            or any(char not in "0123456789abcdef" for char in graph_review["source_sha256"])
        ):
            raise ValueError("BYM2 requires review metadata for this geography and graph source")
    import arviz as az
    import pymc as pm

    with pm.Model():
        intercept = pm.Normal("intercept", mu=-4, sigma=2)
        beta = pm.Normal("beta", mu=0, sigma=1, shape=2)
        if likelihood == "negative_binomial":
            alpha = pm.HalfNormal("alpha", sigma=10)
        fixed = np.log(exposure) + intercept + pm.math.dot(design, beta)
        reference = pm.Deterministic("reference_mu", pm.math.exp(fixed))
        effect = 0
        if variant != "NB":
            basis = scaled_icar_basis(ids, edges)
            sigma = pm.HalfNormal("sigma", sigma=0.5 if variant == "BYM2_SHRINKAGE" else 1)
            rho = pm.Beta("rho", alpha=0.5, beta=0.5)
            z = pm.Normal("spatial_z", 0, 1, shape=basis.shape[1])
            theta = pm.Normal("unstructured", 0, 1, shape=len(areas))
            effect = sigma * (
                pm.math.sqrt(rho) * pm.math.dot(basis, z) + pm.math.sqrt(1 - rho) * theta
            )
        mu = reference if variant == "NB" else pm.math.exp(fixed + effect)
        if likelihood == "negative_binomial":
            pm.NegativeBinomial("bookings", mu=mu[training], alpha=alpha, observed=y[training])
        else:
            pm.Poisson("bookings", mu=mu[training], observed=y[training])
        trace = pm.sample(
            draws=config.draws,
            tune=config.tune,
            chains=config.chains,
            cores=config.cores,
            random_seed=config.seed,
            target_accept=config.target_accept,
            progressbar=False,
            compute_convergence_checks=True,
            return_inferencedata=True,
        )
    names = ["intercept", "beta"] + (["alpha"] if likelihood == "negative_binomial" else [])
    if variant != "NB":
        names += ["sigma", "rho", "spatial_z", "unstructured"]
    rhat_parts = [az.rhat(trace, var_names=[name])[name].values for name in names]
    ess_parts = [az.ess(trace, var_names=[name], method="bulk")[name].values for name in names]
    defined = all(
        values.size > 0 and np.all(np.isfinite(values)) for values in [*rhat_parts, *ess_parts]
    )
    rhat = max(float(values.max()) for values in rhat_parts) if defined else None
    ess = min(float(values.min()) for values in ess_parts) if defined else None
    divergences = int(trace.sample_stats.diverging.sum())
    accepted = (
        defined
        and rhat is not None
        and ess is not None
        and rhat <= config.max_rhat
        and ess >= config.minimum_bulk_ess
        and divergences == 0
    )
    draws = trace.posterior.reference_mu.values.reshape(-1, len(areas))
    if np.any(~np.isfinite(draws)) or np.any(draws <= 0):
        raise ValueError("Non-finite or zero reference posterior")
    tail = (1 - config.credible_mass) / 2
    scores = {}
    holdout_set = set(holdout_ids)
    for i, area in enumerate(areas):
        if area.ward_id not in holdout_set:
            continue
        ratio = area.bookings / draws[:, i]
        lower, center, upper = np.quantile(ratio, [tail, 0.5, 1 - tail])
        scores[area.ward_id] = {
            "expected": float(np.median(draws[:, i])),
            "ratio": float(center),
            "ratio_lower": float(lower),
            "ratio_upper": float(upper),
            "interval_kind": "POSTERIOR_REFERENCE_MEAN_RATIO_NOT_REPORTING_PROBABILITY",
        }
    return {
        "status": "COMPLETE" if accepted else "DIAGNOSTICS_FAILED",
        "variant": variant,
        "max_rhat": rhat,
        "minimum_bulk_ess": ess,
        "divergences": divergences,
        "chains": config.chains,
        "draws_per_chain": config.draws,
        "tune": config.tune,
        "seed": config.seed,
        "holdout_ids": sorted(holdout_ids),
        "graph_review": graph_review if variant != "NB" else None,
        "prediction_scope": "HELDOUT_ONLY",
        "reference": "need covariates/exposure with area effect set to zero",
        "likelihood": likelihood,
        "target_accept": config.target_accept,
        "priors": {
            "intercept": "Normal(-4,2)",
            "beta": "Normal(0,1)",
            **({"alpha": "HalfNormal(10)"} if likelihood == "negative_binomial" else {}),
            "rho": "Beta(0.5,0.5)",
            "sigma": "HalfNormal(0.5)" if variant == "BYM2_SHRINKAGE" else "HalfNormal(1)",
        },
        "scores": scores,
    }


def fit_crossvalidated_count_model(
    areas,
    edges=(),
    variant="NB",
    config=UNDERSERVED_CONFIG,
    folds=5,
    graph_review=None,
):
    """Return complete out-of-fold ratios or no scores if any fold diagnostics fail."""
    validate_cohort(areas, config)
    if not isinstance(folds, int) or isinstance(folds, bool) or not 2 <= folds <= len(areas):
        raise ValueError("Cross-validation folds must be between 2 and the cohort size")
    largest_holdout = math.ceil(len(areas) / folds)
    if len(areas) - largest_holdout < config.minimum_areas - 1:
        raise ValueError(
            "Cross-validation leaves too few training areas for the configured minimum"
        )
    ids = sorted(area.ward_id for area in areas)
    order = np.random.default_rng(config.seed).permutation(ids)
    holdouts = [list(order[index::folds]) for index in range(folds)]
    merged = {}
    diagnostics = []
    complete = True
    for fold_index, holdout_ids in enumerate(holdouts):
        fold_config = replace(config, seed=config.seed + fold_index)
        result = fit_count_model(
            areas,
            edges=edges,
            variant=variant,
            config=fold_config,
            holdout_ids=holdout_ids,
            graph_review=graph_review,
        )
        diagnostics.append({key: value for key, value in result.items() if key != "scores"})
        if result["status"] != "COMPLETE" or set(result["scores"]) != set(holdout_ids):
            complete = False
        overlap = set(merged) & set(result["scores"])
        if overlap:
            raise ValueError("Cross-validation produced duplicate held-out scores")
        merged.update(result["scores"])
    complete = complete and set(merged) == set(ids)
    return {
        "status": "COMPLETE" if complete else "DIAGNOSTICS_FAILED",
        "variant": variant,
        "prediction_scope": "OUT_OF_FOLD",
        "folds": folds,
        "scores": merged if complete else {},
        "fold_diagnostics": diagnostics,
    }
