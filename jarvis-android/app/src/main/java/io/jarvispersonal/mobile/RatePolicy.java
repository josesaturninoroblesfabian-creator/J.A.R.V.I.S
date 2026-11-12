package io.jarvispersonal.mobile;

public final class RatePolicy {
    private RatePolicy() {}
    public static long seconds(String value) {
        try { double n=Double.parseDouble(value); return Double.isFinite(n) ? Math.max(1, Math.min(86400,(long)Math.ceil(n))) : 60; }
        catch(Exception e) { return 60; }
    }
    public static String message(long seconds) { return "Groq alcanzó su límite temporal. Espera unos " + seconds + " segundos y vuelve a intentarlo. Las herramientas locales siguen disponibles."; }
}
