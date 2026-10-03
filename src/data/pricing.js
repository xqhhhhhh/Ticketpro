export function hasPricing(product) {
  return product?.pricing?.some((tier) => Number.isFinite(tier.price)) ?? false;
}

export function startingPrice(product) {
  return Math.min(...product.pricing.filter((tier) => Number.isFinite(tier.price)).map((tier) => tier.price));
}
