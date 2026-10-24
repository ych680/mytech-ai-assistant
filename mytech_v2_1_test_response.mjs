// Render-only cleanup. Exact identity, category, price and source are untouched.
// Keep the original validated output/history so citation provenance is retained.
export function stripTestCitationMarkers(text) {
  if (typeof text !== "string") return text;
  return text.replace(/\[citation:\s*\d+(?:\s*[,，]\s*\d+)*\]/gi, "")
    .replace(/【\d+†[^】\r\n]+】/g, "")
    .replace(/\uE200cite\uE202[^\uE201\r\n]*\uE201/g, "")
    .replace(/[ \t]+(?=[.,;:!?])/g, "").trim();
}

export function testDisplayOutput(output) {
  if (!output || typeof output !== "object" || Array.isArray(output)) return output;
  return { ...output, answer: stripTestCitationMarkers(output.answer), next_step: stripTestCitationMarkers(output.next_step),
    recommendations: Array.isArray(output.recommendations) ? output.recommendations.map(item =>
      item && typeof item === "object" && !Array.isArray(item) ? { ...item, reason: stripTestCitationMarkers(item.reason) } : item) : output.recommendations };
}
