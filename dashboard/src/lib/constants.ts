export interface FieldDef {
  key: string;
  label: string;
  type: "text" | "url" | "boolean" | "json" | "date" | "rating" | "phone" | "email" | "tags" | "number";
}

export interface FieldSection {
  title: string;
  icon: string;
  fields: FieldDef[];
}

export const LEAD_SECTIONS: FieldSection[] = [
  {
    title: "Contact Information",
    icon: "Phone",
    fields: [
      { key: "businessName", label: "Business Name", type: "text" },
      { key: "phone", label: "Phone", type: "phone" },
      { key: "email", label: "Email", type: "email" },
      { key: "emailVerified", label: "Email Verified", type: "boolean" },
      { key: "website", label: "Website", type: "url" },
      { key: "address", label: "Address", type: "text" },
      { key: "city", label: "City", type: "text" },
      { key: "state", label: "State", type: "text" },
      { key: "zipCode", label: "ZIP Code", type: "text" },
      { key: "country", label: "Country", type: "text" },
    ],
  },
  {
    title: "Owner / Decision Maker",
    icon: "User",
    fields: [
      { key: "ownerName", label: "Owner Name", type: "text" },
      { key: "ownerTitle", label: "Title", type: "text" },
      { key: "ownerEmail", label: "Owner Email", type: "email" },
      { key: "ownerEmailVerified", label: "Owner Email Verified", type: "boolean" },
      { key: "ownerPhone", label: "Owner Phone", type: "phone" },
      { key: "ownerLinkedin", label: "LinkedIn", type: "url" },
    ],
  },
  {
    title: "Business Details",
    icon: "Building2",
    fields: [
      { key: "category", label: "Category", type: "text" },
      { key: "subcategory", label: "Subcategory", type: "text" },
      { key: "industryTags", label: "Industry Tags", type: "tags" },
      { key: "employeeCount", label: "Employees", type: "text" },
      { key: "annualRevenueEstimate", label: "Est. Revenue", type: "text" },
      { key: "yearEstablished", label: "Year Established", type: "number" },
      { key: "businessType", label: "Business Type", type: "text" },
      { key: "priceLevel", label: "Price Level", type: "text" },
      { key: "description", label: "Description", type: "text" },
      { key: "serviceOptions", label: "Service Options", type: "json" },
      { key: "businessHours", label: "Business Hours", type: "json" },
      { key: "photoCount", label: "Photo Count", type: "number" },
    ],
  },
  {
    title: "Social Media",
    icon: "Share2",
    fields: [
      { key: "facebookUrl", label: "Facebook", type: "url" },
      { key: "instagramUrl", label: "Instagram", type: "url" },
      { key: "twitterUrl", label: "Twitter / X", type: "url" },
      { key: "linkedinUrl", label: "LinkedIn", type: "url" },
      { key: "youtubeUrl", label: "YouTube", type: "url" },
      { key: "tiktokUrl", label: "TikTok", type: "url" },
    ],
  },
  {
    title: "Tech Stack",
    icon: "Code",
    fields: [
      { key: "hasWebsite", label: "Has Website", type: "boolean" },
      { key: "websitePlatform", label: "Platform", type: "text" },
      { key: "hasSsl", label: "SSL", type: "boolean" },
      { key: "mobileFriendly", label: "Mobile Friendly", type: "boolean" },
      { key: "techStack", label: "Tech Stack", type: "json" },
    ],
  },
  {
    title: "Reviews & Ratings",
    icon: "Star",
    fields: [
      { key: "googleRating", label: "Google Rating", type: "rating" },
      { key: "googleReviewCount", label: "Google Reviews", type: "number" },
      { key: "yelpRating", label: "Yelp Rating", type: "rating" },
      { key: "yelpReviewCount", label: "Yelp Reviews", type: "number" },
      { key: "bbbRating", label: "BBB Rating", type: "text" },
      { key: "bbbAccredited", label: "BBB Accredited", type: "boolean" },
    ],
  },
  {
    title: "Location & Maps",
    icon: "MapPin",
    fields: [
      { key: "latitude", label: "Latitude", type: "number" },
      { key: "longitude", label: "Longitude", type: "number" },
      { key: "googlePlaceId", label: "Google Place ID", type: "text" },
    ],
  },
  {
    title: "Ad Intelligence",
    icon: "Megaphone",
    fields: [
      { key: "runsGoogleAds", label: "Google Ads", type: "boolean" },
      { key: "runsFacebookAds", label: "Facebook Ads", type: "boolean" },
      { key: "hasGoogleBusinessProfile", label: "Google Business Profile", type: "boolean" },
    ],
  },
  {
    title: "Metadata",
    icon: "Info",
    fields: [
      { key: "source", label: "Source", type: "text" },
      { key: "sourceUrl", label: "Source URL", type: "url" },
      { key: "scrapedAt", label: "Scraped At", type: "date" },
      { key: "enrichedAt", label: "Enriched At", type: "date" },
      { key: "lastEnrichedAt", label: "Last Re-Enriched", type: "date" },
      { key: "updatedAt", label: "Updated At", type: "date" },
      { key: "isEnriched", label: "Enriched", type: "boolean" },
      { key: "qualityScore", label: "Quality Score", type: "number" },
      { key: "icpScore", label: "ICP Score", type: "number" },
      { key: "enrichmentErrors", label: "Enrichment Errors", type: "text" },
    ],
  },
];
