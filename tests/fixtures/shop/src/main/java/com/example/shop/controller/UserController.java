package com.example.shop.controller;

import com.example.shop.dto.UserDTO;
import com.example.shop.service.UserService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/api/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    @GetMapping
    public List<UserDTO> list() {
        return userService.findAll();
    }

    @GetMapping("/{id}")
    public ResponseEntity<UserDTO> getUser(@PathVariable Long id) {
        return ResponseEntity.ok(userService.findById(id));
    }

    @PostMapping
    public ResponseEntity<UserDTO> create(@Valid @RequestBody UserDTO dto,
                                          @RequestParam(defaultValue = "false") boolean notify) {
        return ResponseEntity.status(201).body(dto);
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    @DeleteMapping(value = "/{id}")
    public void delete(@PathVariable("id") Long id) {
    }
}
