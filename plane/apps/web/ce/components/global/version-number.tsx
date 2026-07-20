/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// assets
import packageJson from "package.json";
import { MESH_GITHUB_URL, MESH_SOURCE_NOTICE } from "@/constants/mesh";

export function PlaneVersionNumber() {
  return (
    <a
      href={MESH_GITHUB_URL}
      target="_blank"
      rel="noopener noreferrer"
      className="flex flex-col gap-0.5"
    >
      <span className="text-primary">Mesh Console v{packageJson.version}</span>
      <span>{MESH_SOURCE_NOTICE}</span>
    </a>
  );
}
