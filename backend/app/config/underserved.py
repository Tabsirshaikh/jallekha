"""E5 engineering defaults; thresholds are review policy, not entitlements."""

from dataclasses import dataclass


@dataclass(frozen=True)
class UnderservedConfig:
    minimum_areas: int = 20
    peer_count: int = 5
    ratio_quantile: float = 0.20
    wad_quantile: float = 0.75
    max_reference_age_years: int = 2
    # Need shares (WAD, non-tap, CAD, hardship) are structural and only Census 2011 has them by
    # ward, so they may be older than household counts. Basis: ASSUMED; flagged on every row.
    max_need_reference_age_years: int = 15
    credible_mass: float = 0.95
    chains: int = 2
    draws: int = 1000
    tune: int = 1000
    seed: int = 20261002
    max_rhat: float = 1.01
    minimum_bulk_ess: float = 100
    max_model_areas: int = 250
    # NUTS step-size target (higher = smaller steps, fewer divergences, slower). Basis: ASSUMED.
    target_accept: float = 0.95
    # Chains run in parallel on this many cores; results are seeded per chain. Basis: ASSUMED.
    cores: int = 1
    # Count model for the BYM2 variants: "negative_binomial" (original E5 spec) or "poisson"
    # (Riebler et al. 2016 BYM2, where the random effects carry the extra variation).
    bym2_likelihood: str = "negative_binomial"
    # Prior on the BYM2 mixing parameter: "beta" = Beta(0.5, 0.5) (original E5 spec) or "pc" =
    # penalised-complexity prior, U = 0.5, alpha = 2/3 (Riebler et al. 2016).
    bym2_rho_prior: str = "beta"
    # Restricted spatial regression (Hodges & Reich 2010): area effects projected off the
    # intercept and need covariates, so they cannot absorb the need effect.
    bym2_restricted: bool = False
    # Islands (wards with no neighbour in the cohort) get no structured effect
    # (Freni-Sterrantino et al. 2018).
    bym2_islands_iid_only: bool = False
    # Area-effect structure for the spatial variants: "bym2" = structured + unstructured (original
    # E5 spec) or "icar" = structured only. With a negative-binomial likelihood the unstructured
    # term duplicates alpha (per-ward extra variation); the E5 diagnosis found alpha unidentified.
    bym2_structure: str = "bym2"
    # Prior on the NB overdispersion: "halfnormal" = HalfNormal(10) on alpha (original E5 spec) or
    # "inv_sqrt" = HalfNormal(1) on 1/sqrt(alpha), where 0 = Poisson (Stan prior-choice
    # recommendations). The E5 diagnosis found alpha the last parameter to mix.
    nb_dispersion_prior: str = "halfnormal"
    geography_version: str = "GHMC_2016_150"


UNDERSERVED_CONFIG = UnderservedConfig()
