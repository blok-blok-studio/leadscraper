import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

/**
 * DELETE /api/leads
 * Body: { ids: number[] }
 * Deletes one or more leads by ID.
 */
export async function DELETE(request: NextRequest) {
  try {
    const body = await request.json();
    const ids: number[] = body.ids;

    if (!ids || !Array.isArray(ids) || ids.length === 0) {
      return NextResponse.json(
        { error: "ids array is required" },
        { status: 400 }
      );
    }

    // Validate all IDs are numbers
    const validIds = ids.filter((id) => typeof id === "number" && id > 0);
    if (validIds.length === 0) {
      return NextResponse.json(
        { error: "No valid IDs provided" },
        { status: 400 }
      );
    }

    const result = await prisma.lead.deleteMany({
      where: { id: { in: validIds } },
    });

    return NextResponse.json({
      deleted: result.count,
      ids: validIds,
    });
  } catch (error) {
    console.error("Delete leads error:", error);
    return NextResponse.json(
      { error: "Failed to delete leads" },
      { status: 500 }
    );
  }
}
