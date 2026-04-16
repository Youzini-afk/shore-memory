//! Scoring utilities shared by Stage 2 recall recipes.
//!
//! Port of Mem0's `mem0/utils/scoring.py` adapted to shore-memory's additive
//! fusion model. Provides:
//! - [`bm25_params_for_query`]: query-length-adaptive sigmoid parameters.
//! - [`normalize_bm25`]: sigmoid normalization of raw BM25 scores into `[0, 1]`.
//! - [`entity_spread_attenuation`]: damping factor for high-connectivity entities.
//! - [`additive_fuse`]: combined scoring over semantic + BM25 + entity + contiguity.
//!
//! The fusion formula is:
//!
//! ```text
//! combined = (semantic + w_b * bm25 + w_e * entity + w_c * contiguity) / divisor
//! divisor  = 1 + (w_b>0?w_b:0) + (w_e>0?w_e:0) + (w_c>0?w_c:0)
//! ```
//!
//! which keeps `combined` in `[0, 1]` when every signal is in `[0, 1]`.

use crate::types::RecallRecipe;

/// Pick sigmoid parameters `(midpoint, steepness)` based on query length.
///
/// Longer queries accumulate larger raw BM25 totals, so the midpoint is
/// shifted up and the curve flattened. Values mirror Mem0's
/// `utils/scoring.py:get_bm25_params`.
pub fn bm25_params_for_query(query: &str) -> (f32, f32) {
    let num_terms = query.split_whitespace().count().max(1);
    if num_terms <= 3 {
        (5.0, 0.7)
    } else if num_terms <= 6 {
        (7.0, 0.6)
    } else if num_terms <= 9 {
        (9.0, 0.5)
    } else if num_terms <= 15 {
        (10.0, 0.5)
    } else {
        (12.0, 0.5)
    }
}

/// Normalize a raw BM25 score into `[0, 1]` via a logistic sigmoid.
pub fn normalize_bm25(raw_score: f32, midpoint: f32, steepness: f32) -> f32 {
    1.0 / (1.0 + (-(steepness * (raw_score - midpoint))).exp())
}

/// Entity spread attenuation.
///
/// An entity linked to many memories (think "User" or a group name) would push
/// every linked memory to the top if we naively added its raw similarity to
/// the combined score. Attenuating by `1 / (1 + 0.001 * (N - 1)²)` keeps the
/// boost meaningful for well-connected-but-specific entities and near-zero for
/// universal ones.
///
/// - `linked_count = 1` → `1.0`
/// - `linked_count = 32` → `~0.504`
/// - `linked_count = 100` → `~0.092`
pub fn entity_spread_attenuation(linked_count: i64) -> f32 {
    let n = linked_count.max(1) as f32;
    let k = (n - 1.0).max(0.0);
    1.0 / (1.0 + 0.001 * k * k)
}

/// Raw signals entering the additive fusion. Each field is expected to be in
/// `[0, 1]` (BM25 should already be sigmoid-normalized). Values outside that
/// range still work but will skew the divisor math.
#[derive(Debug, Clone, Copy, Default, PartialEq)]
pub struct FusionInputs {
    pub semantic: f32,
    pub bm25: f32,
    pub entity: f32,
    pub contiguity: f32,
}

/// Weights applied to each non-semantic signal. `0.0` disables a signal
/// entirely (both in the numerator and in the adaptive divisor).
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct FusionWeights {
    pub bm25: f32,
    pub entity: f32,
    pub contiguity: f32,
}

impl Default for FusionWeights {
    fn default() -> Self {
        // Stage 2 default: semantic + BM25 only (matches the `Hybrid` recipe).
        Self {
            bm25: 1.0,
            entity: 0.0,
            contiguity: 0.0,
        }
    }
}

impl FusionWeights {
    /// Build weights driven purely by which signals a recipe enables. The
    /// actual entity / contiguity weights (and bm25 toggle) are defined
    /// alongside the recipe enum so they stay in one place.
    pub fn for_recipe(recipe: RecallRecipe, entity_weight: f32, contiguity_weight: f32) -> Self {
        Self {
            bm25: if recipe.use_bm25() { 1.0 } else { 0.0 },
            entity: if recipe.use_entity() { entity_weight } else { 0.0 },
            contiguity: if recipe.use_contiguity() { contiguity_weight } else { 0.0 },
        }
    }

    pub fn divisor(&self) -> f32 {
        let mut d = 1.0;
        if self.bm25 > 0.0 {
            d += self.bm25;
        }
        if self.entity > 0.0 {
            d += self.entity;
        }
        if self.contiguity > 0.0 {
            d += self.contiguity;
        }
        d
    }
}

/// Combine the four signals into a single score in `[0, 1]`.
///
/// Returns `(combined, divisor)` — the divisor is returned so callers can
/// surface it in the `score_breakdown` debug payload.
pub fn additive_fuse(signals: FusionInputs, weights: FusionWeights) -> (f32, f32) {
    let divisor = weights.divisor();
    let numerator = signals.semantic
        + weights.bm25 * signals.bm25
        + weights.entity * signals.entity
        + weights.contiguity * signals.contiguity;

    let combined = (numerator / divisor).clamp(0.0, 1.0);
    (combined, divisor)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bm25_params_scale_with_query_length() {
        assert_eq!(bm25_params_for_query("one").0, 5.0);
        assert_eq!(bm25_params_for_query("one two three four").0, 7.0);
        assert_eq!(bm25_params_for_query(&"word ".repeat(20)).0, 12.0);
    }

    #[test]
    fn normalize_bm25_is_monotone_in_zero_one() {
        let lo = normalize_bm25(0.0, 5.0, 0.7);
        let hi = normalize_bm25(10.0, 5.0, 0.7);
        assert!(lo < hi);
        assert!((0.0..=1.0).contains(&lo));
        assert!((0.0..=1.0).contains(&hi));
    }

    #[test]
    fn entity_attenuation_dampens_high_connectivity() {
        let one = entity_spread_attenuation(1);
        let ten = entity_spread_attenuation(10);
        let hundred = entity_spread_attenuation(100);
        assert!((one - 1.0).abs() < 1e-6);
        assert!(ten < one);
        assert!(hundred < ten);
    }

    #[test]
    fn additive_fuse_uses_adaptive_divisor() {
        // Semantic-only: divisor = 1.
        let semantic_only = additive_fuse(
            FusionInputs { semantic: 0.8, ..Default::default() },
            FusionWeights { bm25: 0.0, entity: 0.0, contiguity: 0.0 },
        );
        assert!((semantic_only.0 - 0.8).abs() < 1e-6);
        assert!((semantic_only.1 - 1.0).abs() < 1e-6);

        // Semantic + BM25: divisor = 2.
        let hybrid = additive_fuse(
            FusionInputs { semantic: 0.6, bm25: 0.4, ..Default::default() },
            FusionWeights { bm25: 1.0, entity: 0.0, contiguity: 0.0 },
        );
        assert!((hybrid.1 - 2.0).abs() < 1e-6);
        assert!((hybrid.0 - 0.5).abs() < 1e-6);

        // Semantic + BM25 + entity(0.5): divisor = 2.5.
        let entity_heavy = additive_fuse(
            FusionInputs { semantic: 0.6, bm25: 0.4, entity: 1.0, ..Default::default() },
            FusionWeights { bm25: 1.0, entity: 0.5, contiguity: 0.0 },
        );
        assert!((entity_heavy.1 - 2.5).abs() < 1e-6);
        // raw = 0.6 + 1.0 * 0.4 + 0.5 * 1.0 = 1.5; combined = 1.5 / 2.5 = 0.6
        assert!((entity_heavy.0 - 0.6).abs() < 1e-6);
    }

    #[test]
    fn weights_for_recipe_matches_expectation() {
        let fast = FusionWeights::for_recipe(RecallRecipe::Fast, 0.5, 0.3);
        assert_eq!(fast, FusionWeights { bm25: 0.0, entity: 0.0, contiguity: 0.0 });
        assert!((fast.divisor() - 1.0).abs() < 1e-6);

        let hybrid = FusionWeights::for_recipe(RecallRecipe::Hybrid, 0.5, 0.3);
        assert_eq!(hybrid, FusionWeights { bm25: 1.0, entity: 0.0, contiguity: 0.0 });
        assert!((hybrid.divisor() - 2.0).abs() < 1e-6);

        let entity_heavy = FusionWeights::for_recipe(RecallRecipe::EntityHeavy, 0.5, 0.3);
        assert_eq!(entity_heavy, FusionWeights { bm25: 1.0, entity: 0.5, contiguity: 0.0 });
        assert!((entity_heavy.divisor() - 2.5).abs() < 1e-6);

        let contiguous = FusionWeights::for_recipe(RecallRecipe::Contiguous, 0.5, 0.3);
        assert_eq!(contiguous, FusionWeights { bm25: 1.0, entity: 0.0, contiguity: 0.3 });
        assert!((contiguous.divisor() - 2.3).abs() < 1e-6);
    }
}
