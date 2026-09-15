export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

/**
 * Universal fetch wrapper for API communication.
 * Automatically injects the JWT Authorization Bearer header if present.
 */
export async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const token = localStorage.getItem("token");

  const headers = {
    ...options.headers,
  };

  // If sending JSON body and content-type is not set, default to application/json
  if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    // Handle 401 Unauthorized globally (clear stale token if requested)
    if (response.status === 401 && !endpoint.includes("/auth/login") && !endpoint.includes("/auth/register")) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
    }

    // Handle non-JSON responses (e.g. CSV or PDF blobs)
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("text/csv") || contentType.includes("application/pdf")) {
      if (!response.ok) {
        throw new Error(`Export failed with status ${response.status}`);
      }
      return response.blob();
    }

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const errorMsg = data.detail || (typeof data === "string" ? data : `Request failed with status ${response.status}`);
      const err = new Error(errorMsg);
      err.status = response.status;
      err.data = data;
      throw err;
    }

    return data;
  } catch (error) {
    if (error.name === "TypeError" && error.message.includes("fetch")) {
      throw new Error("Unable to connect to the server. Please ensure the backend is running at http://localhost:8000.");
    }
    throw error;
  }
}

export const authApi = {
  login: async (email, password) => {
    return apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  register: async (email, password) => {
    return apiRequest("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, role: "member" }),
    });
  },

  getProfile: async () => {
    return apiRequest("/auth/me", {
      method: "GET",
    });
  },
};

export const meetingsApi = {
  list: async (params = {}) => {
    const query = new URLSearchParams();
    if (params.page) query.append("page", params.page);
    if (params.pageSize) query.append("page_size", params.pageSize);
    if (params.search) query.append("search", params.search);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return apiRequest(`/meetings${qs}`, { method: "GET" });
  },

  getById: async (id) => {
    return apiRequest(`/meetings/${id}`, { method: "GET" });
  },

  getRecurring: async (id) => {
    return apiRequest(`/meetings/${id}/recurring-items`, { method: "GET" });
  },

  createJson: async (payload) => {
    return apiRequest("/meetings", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  createFormData: async (formData) => {
    return apiRequest("/meetings", {
      method: "POST",
      body: formData,
    });
  },
};

export const actionItemsApi = {
  list: async (filters = {}) => {
    const query = new URLSearchParams();
    if (filters.status) query.append("status", filters.status);
    if (filters.owner) query.append("owner", filters.owner);
    if (filters.category) query.append("category", filters.category);
    if (filters.needs_clarification !== undefined && filters.needs_clarification !== null && filters.needs_clarification !== "") {
      query.append("needs_clarification", filters.needs_clarification);
    }
    if (filters.overdue !== undefined && filters.overdue !== null && filters.overdue !== "") {
      query.append("overdue", filters.overdue);
    }
    const qs = query.toString() ? `?${query.toString()}` : "";
    return apiRequest(`/action-items${qs}`, { method: "GET" });
  },

  update: async (id, updates) => {
    return apiRequest(`/action-items/${id}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    });
  },

  confirm: async (id) => {
    return apiRequest(`/action-items/${id}/confirm`, {
      method: "POST",
    });
  },

  merge: async (primaryId, duplicateId) => {
    return apiRequest("/action-items/merge", {
      method: "POST",
      body: JSON.stringify({ primary_id: primaryId, duplicate_id: duplicateId }),
    });
  },

  getDuplicates: async (id) => {
    return apiRequest(`/action-items/duplicates/${id}`, {
      method: "GET",
    });
  },
};

export const decisionsApi = {
  list: async (meetingId = null) => {
    const qs = meetingId ? `?meeting_id=${meetingId}` : "";
    return apiRequest(`/decisions${qs}`, { method: "GET" });
  },
};

export const statsApi = {
  getStats: async () => {
    return apiRequest("/stats", { method: "GET" });
  },
};

export const calendarApi = {
  getCalendar: async () => {
    return apiRequest("/calendar", { method: "GET" });
  },
};

export const exportApi = {
  downloadCsv: async (meetingId, title = "meeting") => {
    const blob = await apiRequest(`/export/${meetingId}`, { method: "GET" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${title.toLowerCase().replace(/\s+/g, "_")}_meeting_${meetingId}_action_items.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  },

  downloadPdf: async (meetingId, title = "meeting") => {
    const blob = await apiRequest(`/export/${meetingId}/pdf`, { method: "GET" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${title.toLowerCase().replace(/\s+/g, "_")}_meeting_${meetingId}_action_items.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  },
};

export const settingsApi = {
  getSettings: async () => {
    return apiRequest("/settings", { method: "GET" });
  },

  updateSettings: async (settings) => {
    return apiRequest("/settings", {
      method: "PATCH",
      body: JSON.stringify(settings),
    });
  },
};
