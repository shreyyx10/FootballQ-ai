import { Container } from "@/components/layout/Container";
import { ButtonLink } from "@/components/ui/Button";

export default function NotFound() {
  return (
    <Container className="flex flex-col items-center justify-center py-24 text-center">
      <p className="text-sm font-semibold uppercase tracking-wide text-accent">404</p>
      <h1 className="mt-2 text-3xl font-bold text-foreground sm:text-4xl">Page not found</h1>
      <p className="mt-3 max-w-md text-foreground-muted">
        The page you&apos;re looking for doesn&apos;t exist. Head back to the
        homepage or try Q Scout.
      </p>
      <div className="mt-6 flex gap-3">
        <ButtonLink href="/">Back to home</ButtonLink>
        <ButtonLink href="/scout" variant="secondary">
          Try Q Scout
        </ButtonLink>
      </div>
    </Container>
  );
}
