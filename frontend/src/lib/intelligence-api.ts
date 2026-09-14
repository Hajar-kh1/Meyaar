import { getAuthToken } from "@/lib/api";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";

function headers(): HeadersInit {
  const token = getAuthToken();

  return token
    ? { Authorization: `Bearer ${token}` }
    : {};
}

async function parse<T>(
  response: Response
): Promise<T> {
  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;

    try {
      const body = await response.json();

      if (body?.detail) {
        message =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail);
      }
    } catch {}

    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export interface GeoSASource {
  document: string;
  page: number;
  excerpt: string;
  score: number;
}

export interface GeoSAResponse {
  answer: string;
  sources: GeoSASource[];
  attachment?: string;
}

export interface POIResponse {
  filename: string;
  question: string;
  selected_tools: string[];
  tool_results: {
    poi_quality?: {
      total_pois: number;
      affected_pois: number;
      quality_score: number;
      missing_name_count: number;
      missing_category_count: number;
      missing_coordinates_count: number;
      invalid_coordinates_count: number;
      duplicate_count: number;
      category_distribution: Record<string, number>;
    };
    poi_summary?: {
      total_pois: number;
      category_count: number;
      categories: Record<string, number>;
    };
    geosa_rag?: GeoSASource[];
  };
  answer: string;
  preview_geojson: GeoJSON.FeatureCollection;
}

export interface DatasetCompareResponse {
  dataset_a: {
    name: string;
    feature_count: number;
  };
  dataset_b: {
    name: string;
    feature_count: number;
  };
  compatibility: {
    compatible: boolean;
    level: string;
    score: number;
    geometry_family_a: string | null;
    geometry_family_b: string | null;
    schema_similarity: number;
    spatial_overlap: number;
    reason: string;
  };
  schema: {
    dataset_a_fields: number;
    dataset_b_fields: number;
    common_fields_count: number;
    only_a_count: number;
    only_b_count: number;
    common_fields: string[];
    only_a: string[];
    only_b: string[];
    type_changes: Array<{
      field: string;
      dataset_a: string;
      dataset_b: string;
    }>;
  };
  spatial: {
    matching_strategy: string | null;
    matched_count: number;
    only_a_count: number;
    only_b_count: number;
    geometry_different_count: number;
  };
  quality: {
    dataset_a: {
      total_features: number;
      affected_features: number;
      quality_score: number;
      issues: Record<string, number>;
    };
    dataset_b: {
      total_features: number;
      affected_features: number;
      quality_score: number;
      issues: Record<string, number>;
    };
    change: number;
  };
  compliance: {
    status: string;
    message: string;
  };
  map_layers: {
    only_a: GeoJSON.FeatureCollection;
    only_b: GeoJSON.FeatureCollection;
    matched: GeoJSON.FeatureCollection;
  };
  interpretation: string | null;
}

export interface GeoRFPResponse {
  rfp: string | null;
  status: string;
  sources: GeoSASource[];
}

export async function askGeoSA(
  question: string,
  file?: File | null
): Promise<GeoSAResponse> {
  if (file) {
    const form = new FormData();

    form.append("question", question);
    form.append("top_k", "5");
    form.append("file", file);

    return parse(
      await fetch(
        `${API_BASE_URL}/geosa/ask-file`,
        {
          method: "POST",
          headers: headers(),
          body: form,
        }
      )
    );
  }

  return parse(
    await fetch(
      `${API_BASE_URL}/geosa/ask`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...headers(),
        },
        body: JSON.stringify({
          question,
          top_k: 5,
        }),
      }
    )
  );
}

export async function analyzePOI(
  file: File,
  question: string
): Promise<POIResponse> {
  const form = new FormData();

  form.append("file", file);
  form.append("question", question);

  return parse(
    await fetch(
      `${API_BASE_URL}/intelligence/poi`,
      {
        method: "POST",
        headers: headers(),
        body: form,
      }
    )
  );
}

export async function compareDatasets(
  fileA: File,
  fileB: File
): Promise<DatasetCompareResponse> {
  const form = new FormData();

  form.append("file_a", fileA);
  form.append("file_b", fileB);

  return parse(
    await fetch(
      `${API_BASE_URL}/intelligence/compare`,
      {
        method: "POST",
        headers: headers(),
        body: form,
      }
    )
  );
}

export async function generateGeoRFP(
  projectDescription: string
): Promise<GeoRFPResponse> {
  return parse(
    await fetch(
      `${API_BASE_URL}/intelligence/georfp`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...headers(),
        },
        body: JSON.stringify({
          project_description:
            projectDescription,
          top_k: 8,
        }),
      }
    )
  );
}