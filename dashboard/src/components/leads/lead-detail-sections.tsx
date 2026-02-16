import { ExternalLink, Check, X } from "lucide-react";
import { LEAD_SECTIONS, type FieldDef } from "@/lib/constants";
import { formatPhone, formatDateShort } from "@/lib/utils";

interface LeadDetailSectionsProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  lead: Record<string, any>;
}

function isEmpty(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === "string" && value.trim() === "") return true;
  if (Array.isArray(value) && value.length === 0) return true;
  if (typeof value === "object" && !Array.isArray(value) && !(value instanceof Date)) {
    return Object.keys(value as object).length === 0;
  }
  return false;
}

function renderField(field: FieldDef, value: unknown): React.ReactNode {
  if (isEmpty(value)) return null;

  switch (field.type) {
    case "url":
      return (
        <a
          href={value as string}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-primary hover:underline"
        >
          <span className="max-w-xs truncate">{value as string}</span>
          <ExternalLink className="h-3 w-3 flex-shrink-0" />
        </a>
      );

    case "boolean":
      return value ? (
        <span className="inline-flex items-center gap-1 text-emerald-600">
          <Check className="h-4 w-4" /> Yes
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 text-red-500">
          <X className="h-4 w-4" /> No
        </span>
      );

    case "json": {
      if (typeof value !== "object" || value === null) {
        return <span className="text-card-foreground">{String(value)}</span>;
      }
      const entries = Object.entries(value as Record<string, unknown>);
      if (entries.length === 0) return null;
      return (
        <div className="flex flex-wrap gap-2">
          {entries.map(([k, v]) => (
            <span
              key={k}
              className="inline-flex items-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground"
            >
              {k}: {String(v)}
            </span>
          ))}
        </div>
      );
    }

    case "date":
      return (
        <span className="text-card-foreground">
          {formatDateShort(value as Date | string)}
        </span>
      );

    case "phone":
      return (
        <span className="text-card-foreground">{formatPhone(value as string)}</span>
      );

    case "email":
      return (
        <a
          href={`mailto:${value as string}`}
          className="text-primary hover:underline"
        >
          {value as string}
        </a>
      );

    case "rating": {
      const num = Number(value);
      return (
        <span className="text-card-foreground">
          {num.toFixed(1)} <span className="text-amber-500">&#9733;</span>
        </span>
      );
    }

    case "tags": {
      const tags = Array.isArray(value) ? value : [];
      if (tags.length === 0) return null;
      return (
        <div className="flex flex-wrap gap-1.5">
          {tags.map((tag: string) => (
            <span
              key={tag}
              className="inline-flex items-center rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary"
            >
              {tag}
            </span>
          ))}
        </div>
      );
    }

    case "number":
      return (
        <span className="text-card-foreground">
          {typeof value === "number" ? value.toLocaleString() : String(value)}
        </span>
      );

    case "text":
    default:
      return <span className="text-card-foreground">{String(value)}</span>;
  }
}

export function LeadDetailSections({ lead }: LeadDetailSectionsProps) {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {LEAD_SECTIONS.map((section) => {
        // Filter to only fields that have values
        const fieldsWithValues = section.fields.filter(
          (f) => !isEmpty(lead[f.key]),
        );

        // Skip sections with no data
        if (fieldsWithValues.length === 0) return null;

        return (
          <div
            key={section.title}
            className="bg-card rounded-xl border border-border p-6 shadow-sm"
          >
            <h3 className="mb-4 text-sm font-semibold text-card-foreground">
              {section.title}
            </h3>
            <dl className="space-y-3">
              {fieldsWithValues.map((field) => {
                const rendered = renderField(field, lead[field.key]);
                if (rendered === null) return null;
                return (
                  <div
                    key={field.key}
                    className="flex flex-col gap-1 sm:flex-row sm:items-start sm:gap-4"
                  >
                    <dt className="w-40 flex-shrink-0 text-sm text-muted-foreground">
                      {field.label}
                    </dt>
                    <dd className="min-w-0 flex-1 text-sm break-all">
                      {rendered}
                    </dd>
                  </div>
                );
              })}
            </dl>
          </div>
        );
      })}
    </div>
  );
}
