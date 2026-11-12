package io.jarvispersonal.mobile;

import java.text.Normalizer;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class LocalCommands {
    public record Command(String kind, String value) {}
    private LocalCommands() {}
    public static String plain(String text) {
        return Normalizer.normalize(text.toLowerCase(Locale.ROOT), Normalizer.Form.NFD)
            .replaceAll("\\p{M}", "").trim();
    }
    public static Command parse(String text) {
        String t = plain(text).replaceFirst("^(?:jarvis|yarvis)[, :]*", "").replaceAll("[.!?¿¡]+$", "").trim();
        if (t.matches("(?:enciende|prende|activa|abre)(?: la)? camara")) return new Command("camera", "on");
        if (t.matches("(?:apaga|cierra|desactiva)(?: la)? camara")) return new Command("camera", "off");
        if (t.matches("(?:enciende|prende|activa)(?: la)? linterna")) return new Command("torch", "on");
        if (t.matches("(?:apaga|desactiva)(?: la)? linterna")) return new Command("torch", "off");
        if (t.matches("(?:pausa|pausar)(?: el)? enfoque")) return new Command("focus", "pause");
        if (t.matches("(?:continua|reanuda)(?: el)? enfoque")) return new Command("focus", "resume");
        if (t.matches("(?:termina|deten|cancela)(?: el)? enfoque")) return new Command("focus", "stop");
        if (t.matches("(?:inicia|empieza|activa)(?: el)? enfoque")) return new Command("focus", "25");
        String numbered = t.replace("veinticinco", "25").replace("quince", "15").replace("cincuenta", "50")
            .replace("treinta", "30").replace("cinco", "5").replace("diez", "10");
        Matcher focus = Pattern.compile("^(?:inicia|empieza|activa)(?: una sesion de| el)? enfoque(?: de| por| durante)? (\\d{1,3}) minutos?(?: para .+)?$").matcher(numbered);
        if (focus.matches()) return new Command("focus", focus.group(1));
        if (t.startsWith("calcula ")) return new Command("calculate", t.substring(8).replace(" por ", "*").replace(" entre ", "/"));
        if (t.matches("(?:que hora es|dime la hora|hora)")) return new Command("time", "");
        if (t.matches("(?:cuanta bateria queda|bateria|estado de la bateria)")) return new Command("battery", "");
        if (t.matches("(?:ayuda|que puedes hacer|herramientas)")) return new Command("help", "");
        if (t.startsWith("recuerda que ")) return new Command("remember", text.substring(text.toLowerCase(Locale.ROOT).indexOf("recuerda que ")+12).trim());
        if (t.matches("(?:que recuerdas|muestra mis notas|mis notas)")) return new Command("notes", "");
        Matcher color = Pattern.compile("^(?:cambia|pon|cambiar)(?: el)?(?: color del)? holograma(?: a| de color)? (azul|verde|violeta|rojo|dorado|rosa)$").matcher(t);
        if (color.matches()) return new Command("color", color.group(1));
        return new Command("chat", text);
    }
}
