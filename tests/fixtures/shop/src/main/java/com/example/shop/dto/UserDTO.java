package com.example.shop.dto;

import jakarta.validation.constraints.NotBlank;

public record UserDTO(Long id, @NotBlank String name) {
    public UserDTO {
        if (name == null) name = "";
    }
}
