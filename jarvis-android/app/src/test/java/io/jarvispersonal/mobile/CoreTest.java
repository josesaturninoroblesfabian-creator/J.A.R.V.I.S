package io.jarvispersonal.mobile;

import org.junit.Test;
import static org.junit.Assert.*;
import java.util.*;

public class CoreTest {
    @Test public void calculatorOrderAndParentheses() { assertEquals(3973,Calculator.evaluate("137*29"),0);assertEquals(14,Calculator.evaluate("2*(3+4)"),0);assertEquals(-2,Calculator.evaluate("-5 + 6 / 2"),0); }
    @Test public void calculatorSpanishSymbols() { assertEquals(3,Calculator.evaluate("1,5 × 2"),0);assertEquals(4,Calculator.evaluate("8 ÷ 2"),0); }
    @Test public void calculatorRejectsCode() { assertThrows(IllegalArgumentException.class,()->Calculator.evaluate("Runtime.exec(1)")); }
    @Test public void calculatorRejectsZero() { assertThrows(IllegalArgumentException.class,()->Calculator.evaluate("1/0")); }
    @Test public void calculatorRejectsBrokenInput() { for(String s:List.of("", "(1+2", "1 2", "1..2","2**3","NaN"))assertThrows(s,IllegalArgumentException.class,()->Calculator.evaluate(s)); }
    @Test public void calculatorRejectsDeepInput() { assertThrows(IllegalArgumentException.class,()->Calculator.evaluate("(".repeat(25)+"1"+")".repeat(25))); }
    @Test public void calculatorRejectsHugeInput() { assertThrows(IllegalArgumentException.class,()->Calculator.evaluate("1".repeat(161))); }
    @Test public void cameraLocalWithWakeWord() { assertEquals("camera",LocalCommands.parse("Jarvis, enciende la cámara").kind());assertEquals("on",LocalCommands.parse("abre cámara").value());assertEquals("off",LocalCommands.parse("apaga la cámara.").value()); }
    @Test public void commandsMustBeExplicit() { assertEquals("chat",LocalCommands.parse("¿Por qué no enciende la cámara?").kind());assertEquals("chat",LocalCommands.parse("enciende la cámara y manda una foto").kind()); }
    @Test public void spokenFocus() { assertEquals("25",LocalCommands.parse("inicia enfoque de veinticinco minutos").value());assertEquals("15",LocalCommands.parse("empieza una sesión de enfoque durante quince minutos").value()); }
    @Test public void focusControl() { assertEquals("pause",LocalCommands.parse("pausa el enfoque").value());assertEquals("resume",LocalCommands.parse("continúa el enfoque").value());assertEquals("stop",LocalCommands.parse("termina el enfoque").value()); }
    @Test public void torchLocal() { assertEquals("torch",LocalCommands.parse("enciende la linterna").kind());assertEquals("off",LocalCommands.parse("desactiva linterna").value()); }
    @Test public void memoryPreservesSpanish() { assertEquals("Estudiar programación",LocalCommands.parse("Jarvis, recuerda que Estudiar programación").value()); }
    @Test public void colorLocal() { assertEquals("violeta",LocalCommands.parse("cambia el holograma a violeta").value()); }
    @Test public void historyBounded() { List<ChatMessage> values=new ArrayList<>();for(int i=0;i<30;i++)values.add(new ChatMessage(i%2==0?"user":"assistant","mensaje"));assertEquals(8,ConversationPolicy.recent(values).size()); }
    @Test public void longLatestMessageBounded() { List<ChatMessage> recent=ConversationPolicy.recent(List.of(new ChatMessage("user","a".repeat(5000))));assertEquals(4000,recent.get(0).content.length()); }
    @Test public void historyKeepsOrderAndDisallowsInjectedSystem() { List<ChatMessage> recent=ConversationPolicy.recent(List.of(new ChatMessage("system","bad"),new ChatMessage("user","one"),new ChatMessage("assistant","two")));assertEquals(2,recent.size());assertEquals("one",recent.get(0).content);assertEquals("two",recent.get(1).content); }
    @Test public void notesOnlyAppearWhenSupplied() { assertFalse(ConversationPolicy.system("Ana","Suave","").contains("secret-note"));assertTrue(ConversationPolicy.system("Ana","Suave","secret-note").contains("secret-note"));assertTrue(ConversationPolicy.system("Ana","Suave","").contains("no controla Windows")); }
    @Test public void rateLimitMalformedSafe() { for(String value:Arrays.asList(null,"nonsense","NaN","Infinity"))assertEquals(60,RatePolicy.seconds(value));assertEquals(7,RatePolicy.seconds("6.25"));assertEquals(1,RatePolicy.seconds("-4"));assertEquals(86400,RatePolicy.seconds("9999999")); }
}
