package com.example.shop.util;

public final class DateUtils {
    private DateUtils() {}

    public static String today() {
        return java.time.LocalDate.now().toString();
    }
}
