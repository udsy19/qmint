import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DOC_CONTENT } from "@/components/docs/content";
import { DocPage } from "@/components/docs/doc-page";
import { DOCS, docBySlug } from "@/components/docs/registry";

type Props = { params: Promise<{ slug: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return DOCS.map((d) => ({ slug: d.slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const doc = docBySlug((await params).slug);
  return doc ? { title: `${doc.title} · Docs`, description: doc.description } : {};
}

export default async function DocRoute({ params }: Props) {
  const { slug } = await params;
  const doc = docBySlug(slug);
  const content = DOC_CONTENT[slug];
  if (!doc || !content) notFound();
  return <DocPage doc={doc} content={content} />;
}
