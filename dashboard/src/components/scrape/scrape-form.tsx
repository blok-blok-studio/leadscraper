"use client";

import { useState } from "react";
import {
  Play,
  Loader2,
  MapPin,
  Building2,
  Globe,
  ChevronDown,
  ChevronUp,
  X,
  Search,
} from "lucide-react";

// US States with cities
const US_STATES: Record<string, { name: string; cities: string[] }> = {
  AL: { name: "Alabama", cities: ["Birmingham", "Montgomery", "Huntsville", "Mobile"] },
  AK: { name: "Alaska", cities: ["Anchorage", "Fairbanks", "Juneau"] },
  AZ: { name: "Arizona", cities: ["Phoenix", "Tucson", "Mesa", "Scottsdale"] },
  AR: { name: "Arkansas", cities: ["Little Rock", "Fort Smith", "Fayetteville"] },
  CA: { name: "California", cities: ["Los Angeles", "San Francisco", "San Diego", "San Jose", "Sacramento", "Oakland", "Fresno"] },
  CO: { name: "Colorado", cities: ["Denver", "Colorado Springs", "Aurora", "Fort Collins"] },
  CT: { name: "Connecticut", cities: ["Hartford", "New Haven", "Stamford", "Bridgeport"] },
  DE: { name: "Delaware", cities: ["Wilmington", "Dover", "Newark"] },
  FL: { name: "Florida", cities: ["Miami", "Orlando", "Tampa", "Jacksonville", "Fort Lauderdale", "St Petersburg"] },
  GA: { name: "Georgia", cities: ["Atlanta", "Savannah", "Augusta", "Columbus"] },
  HI: { name: "Hawaii", cities: ["Honolulu", "Hilo", "Kailua"] },
  ID: { name: "Idaho", cities: ["Boise", "Idaho Falls", "Meridian"] },
  IL: { name: "Illinois", cities: ["Chicago", "Springfield", "Naperville", "Rockford"] },
  IN: { name: "Indiana", cities: ["Indianapolis", "Fort Wayne", "Evansville", "South Bend"] },
  IA: { name: "Iowa", cities: ["Des Moines", "Cedar Rapids", "Iowa City"] },
  KS: { name: "Kansas", cities: ["Wichita", "Kansas City", "Topeka", "Overland Park"] },
  KY: { name: "Kentucky", cities: ["Louisville", "Lexington", "Bowling Green"] },
  LA: { name: "Louisiana", cities: ["New Orleans", "Baton Rouge", "Shreveport"] },
  ME: { name: "Maine", cities: ["Portland", "Bangor", "Lewiston"] },
  MD: { name: "Maryland", cities: ["Baltimore", "Annapolis", "Rockville", "Frederick"] },
  MA: { name: "Massachusetts", cities: ["Boston", "Worcester", "Springfield", "Cambridge"] },
  MI: { name: "Michigan", cities: ["Detroit", "Grand Rapids", "Ann Arbor", "Lansing"] },
  MN: { name: "Minnesota", cities: ["Minneapolis", "St Paul", "Rochester", "Duluth"] },
  MS: { name: "Mississippi", cities: ["Jackson", "Gulfport", "Hattiesburg"] },
  MO: { name: "Missouri", cities: ["Kansas City", "St Louis", "Springfield", "Columbia"] },
  MT: { name: "Montana", cities: ["Billings", "Missoula", "Great Falls"] },
  NE: { name: "Nebraska", cities: ["Omaha", "Lincoln", "Bellevue"] },
  NV: { name: "Nevada", cities: ["Las Vegas", "Reno", "Henderson"] },
  NH: { name: "New Hampshire", cities: ["Manchester", "Nashua", "Concord"] },
  NJ: { name: "New Jersey", cities: ["Newark", "Jersey City", "Trenton", "Princeton"] },
  NM: { name: "New Mexico", cities: ["Albuquerque", "Santa Fe", "Las Cruces"] },
  NY: { name: "New York", cities: ["New York", "Buffalo", "Rochester", "Albany", "Syracuse"] },
  NC: { name: "North Carolina", cities: ["Charlotte", "Raleigh", "Durham", "Greensboro", "Wilmington"] },
  ND: { name: "North Dakota", cities: ["Fargo", "Bismarck", "Grand Forks"] },
  OH: { name: "Ohio", cities: ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron"] },
  OK: { name: "Oklahoma", cities: ["Oklahoma City", "Tulsa", "Norman"] },
  OR: { name: "Oregon", cities: ["Portland", "Salem", "Eugene", "Bend"] },
  PA: { name: "Pennsylvania", cities: ["Philadelphia", "Pittsburgh", "Allentown", "Harrisburg"] },
  RI: { name: "Rhode Island", cities: ["Providence", "Warwick", "Cranston"] },
  SC: { name: "South Carolina", cities: ["Charleston", "Columbia", "Greenville", "Myrtle Beach"] },
  SD: { name: "South Dakota", cities: ["Sioux Falls", "Rapid City", "Aberdeen"] },
  TN: { name: "Tennessee", cities: ["Nashville", "Memphis", "Knoxville", "Chattanooga"] },
  TX: { name: "Texas", cities: ["Houston", "Dallas", "Austin", "San Antonio", "Fort Worth", "El Paso"] },
  UT: { name: "Utah", cities: ["Salt Lake City", "Provo", "Ogden", "St George"] },
  VT: { name: "Vermont", cities: ["Burlington", "Montpelier", "Rutland"] },
  VA: { name: "Virginia", cities: ["Richmond", "Virginia Beach", "Arlington", "Norfolk", "Alexandria"] },
  WA: { name: "Washington", cities: ["Seattle", "Tacoma", "Spokane", "Bellevue"] },
  WV: { name: "West Virginia", cities: ["Charleston", "Huntington", "Morgantown"] },
  WI: { name: "Wisconsin", cities: ["Milwaukee", "Madison", "Green Bay"] },
  WY: { name: "Wyoming", cities: ["Cheyenne", "Casper", "Laramie"] },
  DC: { name: "District of Columbia", cities: ["Washington"] },
};

const DEFAULT_CATEGORIES = [
  "Restaurants",
  "Plumbers",
  "Electricians",
  "Dentists",
  "Lawyers",
  "Real Estate Agents",
  "Auto Repair",
  "Salons",
  "Gyms",
  "Accountants",
  "HVAC",
  "Roofers",
  "Landscapers",
  "Chiropractors",
  "Insurance Agents",
  "Veterinarians",
  "Cleaning Services",
  "Pest Control",
  "Moving Companies",
  "Photography",
];

const SOURCES = [
  { value: "googlemaps", label: "Google Maps", available: true },
  { value: "yellowpages", label: "YellowPages", available: true },
  { value: "yelp", label: "Yelp", available: false },
  { value: "bbb", label: "BBB", available: false },
];

interface ScrapeFormProps {
  onSubmit: (params: {
    source: string;
    categories: string[];
    locations: string[];
    pages: number;
  }) => void;
  isRunning: boolean;
}

export function ScrapeForm({ onSubmit, isRunning }: ScrapeFormProps) {
  const [source, setSource] = useState("googlemaps");
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [customCategory, setCustomCategory] = useState("");
  const [selectedStates, setSelectedStates] = useState<string[]>([]);
  const [selectedCities, setSelectedCities] = useState<string[]>([]);
  const [pages, setPages] = useState(3);
  const [showStates, setShowStates] = useState(false);
  const [showCategories, setShowCategories] = useState(false);
  const [stateSearch, setStateSearch] = useState("");
  const [categorySearch, setCategorySearch] = useState("");

  // Build location strings from selected states + cities
  const getLocations = (): string[] => {
    if (selectedCities.length > 0) {
      return selectedCities;
    }
    // If states are selected but no specific cities, use all cities for those states
    const locations: string[] = [];
    for (const stateCode of selectedStates) {
      const state = US_STATES[stateCode];
      if (state) {
        for (const city of state.cities) {
          locations.push(`${city}, ${stateCode}`);
        }
      }
    }
    return locations;
  };

  const handleSubmit = () => {
    const locations = getLocations();
    if (selectedCategories.length === 0 || locations.length === 0) return;

    onSubmit({
      source,
      categories: selectedCategories.map((c) => c.toLowerCase()),
      locations,
      pages,
    });
  };

  const toggleState = (code: string) => {
    setSelectedStates((prev) =>
      prev.includes(code) ? prev.filter((s) => s !== code) : [...prev, code]
    );
    // Clear city selections for this state when toggling
    setSelectedCities((prev) =>
      prev.filter((c) => !c.endsWith(`, ${code}`))
    );
  };

  const toggleCity = (cityLocation: string) => {
    setSelectedCities((prev) =>
      prev.includes(cityLocation)
        ? prev.filter((c) => c !== cityLocation)
        : [...prev, cityLocation]
    );
  };

  const toggleCategory = (cat: string) => {
    setSelectedCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  };

  const addCustomCategory = () => {
    const trimmed = customCategory.trim();
    if (trimmed && !selectedCategories.includes(trimmed)) {
      setSelectedCategories((prev) => [...prev, trimmed]);
      setCustomCategory("");
    }
  };

  const filteredStates = Object.entries(US_STATES).filter(
    ([code, state]) =>
      stateSearch === "" ||
      code.toLowerCase().includes(stateSearch.toLowerCase()) ||
      state.name.toLowerCase().includes(stateSearch.toLowerCase())
  );

  const filteredCategories = DEFAULT_CATEGORIES.filter(
    (cat) =>
      categorySearch === "" ||
      cat.toLowerCase().includes(categorySearch.toLowerCase())
  );

  const totalJobs = selectedCategories.length * (getLocations().length || 0);

  return (
    <div className="space-y-5">
      {/* Source Selection */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="mb-3 flex items-center gap-2">
          <Globe className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-card-foreground">Source</h3>
        </div>
        <div className="flex gap-2">
          {SOURCES.map((s) => (
            <button
              key={s.value}
              onClick={() => s.available && setSource(s.value)}
              disabled={!s.available}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                source === s.value
                  ? "bg-primary text-white"
                  : s.available
                  ? "bg-muted text-card-foreground hover:bg-muted/80"
                  : "cursor-not-allowed bg-muted/50 text-muted-foreground line-through"
              }`}
            >
              {s.label}
              {!s.available && (
                <span className="ml-1 text-xs">(proxy)</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Category Selection */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <button
          onClick={() => setShowCategories(!showCategories)}
          className="flex w-full items-center justify-between"
        >
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold text-card-foreground">
              Categories
            </h3>
            {selectedCategories.length > 0 && (
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                {selectedCategories.length} selected
              </span>
            )}
          </div>
          {showCategories ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>

        {/* Selected category tags */}
        {selectedCategories.length > 0 && !showCategories && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {selectedCategories.map((cat) => (
              <span
                key={cat}
                className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-2 py-1 text-xs font-medium text-primary"
              >
                {cat}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleCategory(cat);
                  }}
                  className="hover:text-primary/70"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ))}
          </div>
        )}

        {showCategories && (
          <div className="mt-3 space-y-3">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={categorySearch}
                onChange={(e) => setCategorySearch(e.target.value)}
                placeholder="Search categories..."
                className="w-full rounded-lg border border-border bg-background py-2 pl-9 pr-3 text-sm text-card-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            {/* Category grid */}
            <div className="grid grid-cols-2 gap-1.5">
              {filteredCategories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => toggleCategory(cat)}
                  className={`rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                    selectedCategories.includes(cat)
                      ? "bg-primary text-white"
                      : "bg-muted/50 text-card-foreground hover:bg-muted"
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            {/* Custom category input */}
            <div className="flex gap-2">
              <input
                type="text"
                value={customCategory}
                onChange={(e) => setCustomCategory(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addCustomCategory()}
                placeholder="Custom category..."
                className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm text-card-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <button
                onClick={addCustomCategory}
                disabled={!customCategory.trim()}
                className="rounded-lg bg-muted px-3 py-2 text-sm font-medium text-card-foreground transition-colors hover:bg-muted/80 disabled:opacity-50"
              >
                Add
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Location Selection */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <button
          onClick={() => setShowStates(!showStates)}
          className="flex w-full items-center justify-between"
        >
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold text-card-foreground">
              Locations
            </h3>
            {(selectedStates.length > 0 || selectedCities.length > 0) && (
              <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-600">
                {selectedCities.length > 0
                  ? `${selectedCities.length} cities`
                  : `${selectedStates.length} states`}
              </span>
            )}
          </div>
          {showStates ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>

        {/* Selected location tags */}
        {(selectedStates.length > 0 || selectedCities.length > 0) &&
          !showStates && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {selectedCities.length > 0
                ? selectedCities.map((city) => (
                    <span
                      key={city}
                      className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-1 text-xs font-medium text-emerald-600"
                    >
                      {city}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleCity(city);
                        }}
                        className="hover:text-emerald-400"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))
                : selectedStates.map((code) => (
                    <span
                      key={code}
                      className="inline-flex items-center gap-1 rounded-md bg-emerald-500/10 px-2 py-1 text-xs font-medium text-emerald-600"
                    >
                      {US_STATES[code]?.name || code}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleState(code);
                        }}
                        className="hover:text-emerald-400"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
            </div>
          )}

        {showStates && (
          <div className="mt-3 space-y-3">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={stateSearch}
                onChange={(e) => setStateSearch(e.target.value)}
                placeholder="Search states..."
                className="w-full rounded-lg border border-border bg-background py-2 pl-9 pr-3 text-sm text-card-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            {/* States + city drill-down */}
            <div className="max-h-72 space-y-1 overflow-y-auto pr-1">
              {filteredStates.map(([code, state]) => (
                <div key={code}>
                  <button
                    onClick={() => toggleState(code)}
                    className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors ${
                      selectedStates.includes(code)
                        ? "bg-emerald-500/10 text-emerald-600"
                        : "text-card-foreground hover:bg-muted/50"
                    }`}
                  >
                    <span>
                      <span className="font-medium">{code}</span>
                      <span className="ml-2 text-muted-foreground">
                        {state.name}
                      </span>
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {state.cities.length} cities
                    </span>
                  </button>

                  {/* Show cities when state is selected */}
                  {selectedStates.includes(code) && (
                    <div className="mb-1 ml-4 mt-1 flex flex-wrap gap-1">
                      {state.cities.map((city) => {
                        const loc = `${city}, ${code}`;
                        const isSelected = selectedCities.includes(loc);
                        return (
                          <button
                            key={loc}
                            onClick={() => toggleCity(loc)}
                            className={`rounded-md px-2.5 py-1 text-xs transition-colors ${
                              isSelected
                                ? "bg-emerald-500 text-white"
                                : "bg-muted/50 text-muted-foreground hover:bg-muted hover:text-card-foreground"
                            }`}
                          >
                            {city}
                          </button>
                        );
                      })}
                      <span className="px-1 py-1 text-xs text-muted-foreground/50">
                        {selectedCities.filter((c) => c.endsWith(`, ${code}`)).length === 0
                          ? "click to pick specific cities, or leave for all"
                          : ""}
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Pages per search */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold text-card-foreground">
          Pages per Search
        </h3>
        <div className="flex items-center gap-3">
          {[1, 2, 3, 5, 10].map((p) => (
            <button
              key={p}
              onClick={() => setPages(p)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                pages === p
                  ? "bg-primary text-white"
                  : "bg-muted text-card-foreground hover:bg-muted/80"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          ~30 leads per page. More pages = more leads but slower.
        </p>
      </div>

      {/* Summary + Launch */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="mb-4 space-y-1 text-sm">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Categories</span>
            <span className="font-medium text-card-foreground">
              {selectedCategories.length}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Locations</span>
            <span className="font-medium text-card-foreground">
              {getLocations().length}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Total jobs to run</span>
            <span className="font-medium text-card-foreground">{totalJobs}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Est. leads</span>
            <span className="font-medium text-card-foreground">
              ~{totalJobs * pages * 30}
            </span>
          </div>
        </div>

        <button
          onClick={handleSubmit}
          disabled={
            isRunning ||
            selectedCategories.length === 0 ||
            getLocations().length === 0
          }
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-3 text-sm font-semibold text-white transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isRunning ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Scraping in progress...
            </>
          ) : (
            <>
              <Play className="h-4 w-4" />
              Launch Scrape
              {totalJobs > 0 && ` (${totalJobs} jobs)`}
            </>
          )}
        </button>
      </div>
    </div>
  );
}
