    function validateProductDataset(dataset) {
      const nonempty = value => typeof value === "string" && value.trim().length > 0;
      const strings = value => Array.isArray(value) && value.length > 0 && value.every(nonempty);
      if (!isPlainObject(dataset) || !Array.isArray(dataset.products)
        || dataset.dataset_name !== TEST_CATALOGUE_CONTRACT.dataset_name
        || dataset.version !== "2.1-TEST" || dataset.currency !== "RMB"
        || dataset.products.length !== TEST_CATALOGUE_CONTRACT.count
        || !nonempty(dataset.snapshot_date) || !nonempty(dataset.price_note)
        || !dataset.price_note.includes("TEST")) throw new Error("INVALID_TEST_PRODUCT_DATASET");
      if (JSON.stringify(dataset.supported_categories) !== JSON.stringify(IDENTITY.supportedCategories)) {
        throw new Error("INVALID_SUPPORTED_CATEGORIES");
      }
      const prefixes = ["LAP", "DES", "PHO", "TAB", "AUD", "MON", "WAT", "MOU", "KEY"];
      const ids = new Set(), names = new Set();
      dataset.products.forEach(product => {
        if (!isPlainObject(product)) throw new Error("INVALID_PRODUCT_DATASET_ENTRY");
        const prefix = prefixes[IDENTITY.supportedCategories.indexOf(product.category)];
        const valid = ["id", "category", "product", "tier", "source", "review_status", "evidence_url", "price_evidence"]
          .every(key => nonempty(product[key]) && product[key] === product[key].trim())
          && IDENTITY.supportedCategories.includes(product.category)
          && new RegExp("^" + prefix + "-[0-9]{3,9}$").test(product.id)
          && Number(product.id.split("-")[1]) > 0
          && Number.isSafeInteger(product.price_rmb) && product.price_rmb > 0
          && ["Entry", "Mid-range", "Premium"].includes(product.tier)
          && ["EXISTING BASELINE", "NEW CANDIDATE — provisional", "NEW CANDIDATE — unverified"].includes(product.review_status)
          && strings(product.main_usage) && strings(product.key_features);
        const name = String(product.product).toLowerCase();
        if (!valid || ids.has(product.id) || names.has(name)) throw new Error("INVALID_PRODUCT_DATASET_ENTRY");
        ids.add(product.id);
        names.add(name);
      });
    }
